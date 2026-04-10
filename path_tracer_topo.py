# path_tracer_topo.py
# Custom Mininet topology for SDN Path Tracing
# Topology:
#
#   h1 --- s1 --- s2 --- h3
#           |      |
#          h2     h4
#
# s1 and s2 connected via OpenFlow to Ryu controller

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink


class PathTracerTopo(Topo):
    def build(self):
        # Add switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Add hosts with static IPs
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        # Add links (with bandwidth limit for iperf testing)
        self.addLink(h1, s1, cls=TCLink, bw=10)
        self.addLink(h2, s1, cls=TCLink, bw=10)
        self.addLink(s1, s2, cls=TCLink, bw=100)
        self.addLink(h3, s2, cls=TCLink, bw=10)
        self.addLink(h4, s2, cls=TCLink, bw=10)


def run():
    setLogLevel('info')
    topo = PathTracerTopo()
    net  = Mininet(
        topo=topo,
        controller=RemoteController('c0', ip='127.0.0.1', port=6653),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False
    )

    net.start()
    info("\n=== SDN Path Tracer Topology Ready ===\n")
    info("Hosts : h1(10.0.0.1)  h2(10.0.0.2)  h3(10.0.0.3)  h4(10.0.0.4)\n")
    info("Switches : s1 <---> s2  (both connected to Ryu on 127.0.0.1:6653)\n")
    info("Run 'pingall' to test, then check /tmp/path_trace.log\n\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
