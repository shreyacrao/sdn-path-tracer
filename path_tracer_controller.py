# path_tracer_controller.py
# SDN Path Tracing Controller using Ryu + OpenFlow 1.3
# Handles: packet_in, flow rule installation, path tracking, logging

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, tcp, udp, icmp, ether_types
import datetime
import json

class PathTracerController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PathTracerController, self).__init__(*args, **kwargs)
        # MAC learning table: {dpid: {mac: port}}
        self.mac_to_port = {}
        # Path log: list of dicts recording each forwarding decision
        self.path_log = []
        self.logger.info("=== SDN Path Tracer Controller Started ===")

    # ── Handshake: install table-miss flow on every switch ───────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser

        # Table-miss: send unmatched packets to controller
        match  = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info("[SWITCH] Connected: dpid=%s", datapath.id)

    # ── Helper: install a flow rule ──────────────────────────────────────────
    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=60, hard_timeout=0):
        ofproto = datapath.ofproto
        parser  = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority,
            idle_timeout=idle_timeout, hard_timeout=hard_timeout,
            match=match, instructions=inst)
        datapath.send_msg(mod)

    # ── Helper: log a forwarding hop ─────────────────────────────────────────
    def _log_path(self, dpid, src_mac, dst_mac, src_ip, dst_ip,
                  in_port, out_port, proto):
        entry = {
            "timestamp": str(datetime.datetime.now()),
            "switch"   : dpid,
            "src_mac"  : src_mac,
            "dst_mac"  : dst_mac,
            "src_ip"   : src_ip,
            "dst_ip"   : dst_ip,
            "in_port"  : in_port,
            "out_port" : str(out_port),
            "protocol" : proto,
        }
        self.path_log.append(entry)
        self.logger.info(
            "[PATH] SW=%s | %s→%s | in=%s out=%s | proto=%s",
            dpid, src_ip or src_mac, dst_ip or dst_mac,
            in_port, out_port, proto)
        # Append to log file for Wireshark-style review
        with open("/tmp/path_trace.log", "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ── Main packet_in handler ───────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg      = ev.msg
        datapath = msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser
        dpid     = datapath.id
        in_port  = msg.match['in_port']

        pkt  = packet.Packet(msg.data)
        eth  = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        # Drop LLDP to avoid flooding logs
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src_mac = eth.src
        dst_mac = eth.dst

        # Learn MAC → port mapping
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        # Determine output port
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # ── Identify Layer-3/4 protocol ──────────────────────────────────────
        ip_pkt  = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        udp_pkt = pkt.get_protocol(udp.udp)
        src_ip  = dst_ip = proto_str = None

        if ip_pkt:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst
            if tcp_pkt:
                proto_str = f"TCP:{tcp_pkt.dst_port}"
            elif udp_pkt:
                proto_str = f"UDP:{udp_pkt.dst_port}"
            else:
                proto_str = "ICMP" if pkt.get_protocol(icmp.icmp) else "IP"
        else:
            proto_str = "ARP" if eth.ethertype == ether_types.ETH_TYPE_ARP \
                        else f"ETH:{eth.ethertype}"

        # ── Install flow rule (only for known unicast destinations) ──────────
        if out_port != ofproto.OFPP_FLOOD and ip_pkt:
            if tcp_pkt:
                match = parser.OFPMatch(
                    in_port=in_port, eth_type=0x0800,
                    ipv4_src=src_ip, ipv4_dst=dst_ip,
                    ip_proto=6, tcp_dst=tcp_pkt.dst_port)
            elif udp_pkt:
                match = parser.OFPMatch(
                    in_port=in_port, eth_type=0x0800,
                    ipv4_src=src_ip, ipv4_dst=dst_ip,
                    ip_proto=17, udp_dst=udp_pkt.dst_port)
            else:
                match = parser.OFPMatch(
                    in_port=in_port, eth_type=0x0800,
                    ipv4_src=src_ip, ipv4_dst=dst_ip)

            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self._add_flow(datapath, priority=10, match=match,
                               actions=actions)
                out_pkt = parser.OFPPacketOut(
                    datapath=datapath, buffer_id=msg.buffer_id,
                    in_port=in_port, actions=actions)
            else:
                self._add_flow(datapath, priority=10, match=match,
                               actions=actions)
                out_pkt = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=in_port, actions=actions,
                    data=msg.data)
        else:
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                out_pkt = parser.OFPPacketOut(
                    datapath=datapath, buffer_id=msg.buffer_id,
                    in_port=in_port, actions=actions)
            else:
                out_pkt = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=in_port, actions=actions,
                    data=msg.data)

        datapath.send_msg(out_pkt)

        # Log the hop
        self._log_path(dpid, src_mac, dst_mac, src_ip, dst_ip,
                       in_port, out_port, proto_str)
