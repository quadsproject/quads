<%
os_major = @host.operatingsystem.major.to_i
%>
# default interface names may get overridden due to foreman templates
# basically this is getting used as a default value.  If we don't know
# what the actual names are for these for a particular node type for
# both RHEL7 and RHEL8 (or any other OS we want to support such as fedora),
# then the NIC will likely not exist and we will fail to setup the
# necessary private networks with the 172.x.x.x addressing, and therefore
# will fail our network connectivity tests (if we care).  This mostly
# matters for quads hosts, and validation testing.
#

nic1=nic1
nic2=nic2
nic3=nic3
nic4=nic4
nic5=nic5

# RHEL9 names defined here
<% if os_major == 9 %>
<% if @host.shortname =~ /r650/ %>
nic1=ens1f0
nic2=ens1f1
nic3=ens2f0np0
nic4=ens2f1np1
nic5=eno12409np1
<% end -%>
<% if @host.shortname =~ /r660/ %>
nic1=ens1f0
nic2=ens1f1
nic3=ens2f0np0
nic4=ens2f1np1
nic5=eno12409np1
<% end -%>
<% if @host.shortname =~ /r730xd/ %>
nic1=eno1
nic2=eno2
nic3=enp130s0f0
nic4=enp130s0f1
<% end -%>
<% if @host.shortname =~ /r750/ %>
nic1=ens3f0
nic2=ens3f1
nic3=ens6f0np0
nic4=ens6f1np1
nic5=eno12409np1
<% end -%>
<% if @host.shortname =~ /r930/ %>
nic1=eno1
nic2=eno2
nic3=enp10s0f0
nic4=enp10s0f1
<% end -%>
<% if @host.shortname =~ /fc640/ %>
<% if @host.shortname =~ /e23-h12/ || @host.shortname =~ /e23-h24/ || @host.shortname =~ /e23-h26/ %>
nic1=eno2
nic2=eth2
nic3=eth3
nic4=ens2f0
nic5=ens2f1
<% else -%>
nic1=eno2
nic2=ens2f0
nic3=ens2f1
<% end -%>
<% end -%>
<% if @host.shortname =~ /dl360/ %>
nic1=ens2f0
nic2=ens2f1
nic3=ens1f0
nic4=ens1f1
nic5=eno6np1
<% end -%>
<% end -%>

<% if os_major == 9 %>
cat > /root/setup-interfaces.sh <<EOS
#!/bin/sh

nic1=$nic1
nic2=$nic2
nic3=$nic3
nic4=$nic4
nic5=$nic5

nics=($nic1 $nic2 $nic3 $nic4 $nic5)
vlans=(101 102 103 104 105)
octets=(16 17 18 19 20)
taggedoctets=(21 22 23 24 25)

for index in 0 1 2 3 4; do
  interface=\${nics[\$index]}
  vlan=\${vlans[\$index]}
  octet=\${octets[\$index]}
  taggedoctet=\${taggedoctets[\$index]}

  /usr/bin/nmcli connection add con-name \$interface ifname \$interface type ethernet
  /usr/bin/nmcli connection modify \$interface ipv4.addresses 172.\$octet.$o3.$o4/16
  /usr/bin/nmcli connection modify \$interface ipv4.method manual
  /usr/bin/nmcli connection up \$interface
  /usr/bin/nmcli connection add type vlan con-name \$interface.\$vlan ifname \$interface.\$vlan vlan.parent \$interface vlan.id \$vlan
  /usr/bin/nmcli connection modify \$interface.\$vlan ipv4.addresses 172.\$taggedoctet.$o3.$o4/16
  /usr/bin/nmcli connection modify \$interface.\$vlan ipv4.method manual
  /usr/bin/nmcli connection up \$interface.\$vlan
done
EOS
<% else -%>
cat > /root/setup-interfaces.sh <<EOS
#!/bin/sh

nic1=$nic1
nic2=$nic2
nic3=$nic3
nic4=$nic4
nic5=$nic5

nics=($nic1 $nic2 $nic3 $nic4 $nic5)
vlans=(101 102 103 104 105)
octets=(16 17 18 19 20)
taggedoctets=(21 22 23 24 25)

for index in 0 1 2 3 4; do
  interface=\${nics[\$index]}
  vlan=\${vlans[\$index]}
  octet=\${octets[\$index]}
  taggedoctet=\${taggedoctets[\$index]}
  ifconfig \$interface 1>/dev/null 2>&1
  cat > /etc/sysconfig/network-scripts/ifcfg-\$interface <<EOF
DEVICE=\$interface
NAME=\$interface
TYPE=Ethernet
BOOTPROTO=static
DEFROUTE=no
ONBOOT=yes
IPADDR=172.\$octet.$o3.$o4
IPV6INIT=no
NETMASK=255.255.0.0
<% if @host.params['nm_disable'] == 'True' %>
NM_CONTROLLED=no
<% end -%>
EOF
  ifup \$interface

    cat > /etc/sysconfig/network-scripts/ifcfg-\$interface.\$vlan <<EOF
DEVICE=\$interface.\$vlan
NAME=\$interface.\$vlan
VLAN=yes
BOOTPROTO=static
DEFROUTE=no
ONBOOT=yes
IPADDR=172.\$taggedoctet.$o3.$o4
IPV6INIT=no
NETMASK=255.255.0.0
<% if @host.params['nm_disable'] == 'True' %>
NM_CONTROLLED=no
<% end -%>
EOF
  ifup \$interface.\$vlan

done
EOS
<% end -%>

chmod 755 /root/setup-interfaces.sh

# https://github.com/redhat-performance/quads/issues/183
<% if os_major == 9 %>
cat > /root/clean-interfaces.sh <<EOS
#!/bin/sh

# Cleanup validation interface configs
#
#
# --nuke = remove interface files completely
# --disable = just stop them from starting at boot

if [[ \$# -eq 0 ]]; then
        echo "USAGE:"
        echo "./clean-interfaces.sh --disable"
	    echo "./clean-interfaces.sh --nuke"
	    exit 1
fi


mode=\$1
disable=false
nuke=false

if [ "\$mode" == "--disable" ]; then
  disable=true
fi

if [ "\$mode" == "--nuke" ]; then
  nuke=true
fi

nic1=$nic1
nic2=$nic2
nic3=$nic3
nic4=$nic4
nic5=$nic5

nics=($nic1 $nic2 $nic3 $nic4 $nic5)
vlans=(101 102 103 104 105)
octets=(16 17 18 19 20)
taggedoctets=(21 22 23 24 25)

for index in 0 1 2 3 4; do
  interface=\${nics[\$index]}
  vlan=\${vlans[\$index]}
  octet=\${octets[\$index]}
  taggedoctet=\${taggedoctets[\$index]}

  if \$disable ; then
    /usr/bin/nmcli connection down \$interface
    /usr/bin/nmcli connection modify \$interface autoconnect false
    /usr/bin/nmcli connection down \$interface.\$vlan
    /usr/bin/nmcli connection modify \$interface.\$vlan autoconnect false
  fi

  if \$nuke ; then
    /usr/bin/nmcli connection down \$interface
    /usr/bin/nmcli connection delete \$interface
    /usr/bin/nmcli connection down \$interface.\$vlan
    /usr/bin/nmcli connection delete \$interface.\$vlan
  fi
done
EOS
<% else -%>
cat > /root/clean-interfaces.sh <<EOS
#!/bin/sh
#
# Cleanup validation interface configs
#
#
# --nuke = remove interface files completely
# --disable = just stop them from starting at boot

if [[ \$# -eq 0 ]]; then
        echo "USAGE:"
        echo "./clean-interfaces.sh --disable"
	    echo "./clean-interfaces.sh --nuke"
	    exit 1
fi


mode=\$1
disable=false
nuke=false

if [ "\$mode" == "--disable" ]; then
  disable=true
fi

if [ "\$mode" == "--nuke" ]; then
  nuke=true
fi

filelist="\$(grep IPADDR=172 /etc/sysconfig/network-scripts/* | awk -F: '{ print \$1 }')"

if \$disable ; then
  for f in \$filelist ; do
    ifdown \$(basename \$f | awk -F- '{ print \$2 }')
    sed -i -e 's/ONBOOT=yes/ONBOOT=no/g' \$f
  done
fi

if \$nuke ; then
  for f in \$filelist ; do
    ifdown \$(basename \$f | awk -F- '{ print \$2 }')
    rm -f \$f
  done
fi

EOS
<% end -%>

chmod 755 /root/clean-interfaces.sh

cat >> /etc/rc.d/rc.local <<EOD
if [ -f /etc/rc.d/rc.network-scripts ]; then
    if [ ! -f /etc/rc.d/.rc.network-scripts ]; then
        . /etc/rc.d/rc.network-scripts
    fi
fi

EOD
chmod +x /etc/rc.d/rc.local

cat > /etc/rc.d/rc.network-scripts <<EOH
# if RHEL8.2 with kmod-ice, we need to modprobe ice
# to ensure interfaces are instantiated
modprobe ice
modprobe ice
sleep 5

if [ -x /root/setup-interfaces.sh ]; then
   /root/setup-interfaces.sh
fi

# remove this file to enable again
touch /etc/rc.d/.rc.network-scripts
EOH
