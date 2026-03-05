"""
VULN-02: SSRF blocklist split tests.

Verifies that ALWAYS_BLOCKED_NETWORKS (cloud metadata, multicast, reserved)
are blocked even when allow_local=True, while LOCAL_NETWORKS (private IPs)
are correctly bypassed for homelab use.
"""

from unittest.mock import patch

import pytest

from splintarr.core.ssrf_protection import (
    ALWAYS_BLOCKED_NETWORKS,
    BLOCKED_NETWORKS,
    LOCAL_NETWORKS,
    SSRFError,
    validate_instance_url,
)


class TestBlocklistSplit:
    """Verify the blocklist is correctly split into always-blocked and local."""

    def test_always_blocked_contains_cloud_metadata(self):
        """169.254.0.0/16 (cloud metadata) must be in ALWAYS_BLOCKED_NETWORKS."""
        network_strs = [str(n) for n in ALWAYS_BLOCKED_NETWORKS]
        assert "169.254.0.0/16" in network_strs

    def test_always_blocked_contains_multicast(self):
        """224.0.0.0/4 (multicast) must be in ALWAYS_BLOCKED_NETWORKS."""
        network_strs = [str(n) for n in ALWAYS_BLOCKED_NETWORKS]
        assert "224.0.0.0/4" in network_strs

    def test_local_networks_contains_private_ranges(self):
        """RFC 1918 private ranges must be in LOCAL_NETWORKS."""
        network_strs = [str(n) for n in LOCAL_NETWORKS]
        assert "10.0.0.0/8" in network_strs
        assert "172.16.0.0/12" in network_strs
        assert "192.168.0.0/16" in network_strs

    def test_local_networks_contains_loopback(self):
        """127.0.0.0/8 (loopback) must be in LOCAL_NETWORKS."""
        network_strs = [str(n) for n in LOCAL_NETWORKS]
        assert "127.0.0.0/8" in network_strs

    def test_blocked_networks_is_combined(self):
        """BLOCKED_NETWORKS must be the union of both lists."""
        assert BLOCKED_NETWORKS == ALWAYS_BLOCKED_NETWORKS + LOCAL_NETWORKS

    def test_no_overlap_between_lists(self):
        """ALWAYS_BLOCKED_NETWORKS and LOCAL_NETWORKS must not overlap."""
        always_set = {str(n) for n in ALWAYS_BLOCKED_NETWORKS}
        local_set = {str(n) for n in LOCAL_NETWORKS}
        overlap = always_set & local_set
        assert not overlap, f"Overlapping networks: {overlap}"


class TestCloudMetadataAlwaysBlocked:
    """VULN-02: Cloud metadata must be blocked even with allow_local=True."""

    def test_cloud_metadata_blocked_even_with_allow_local(self):
        """allow_local must NOT bypass cloud metadata blocking."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("169.254.169.254", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url(
                    "http://169.254.169.254/latest/", allow_local=True
                )

    def test_cloud_metadata_blocked_without_allow_local(self):
        """Cloud metadata must also be blocked when allow_local=False."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("169.254.169.254", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url(
                    "http://169.254.169.254/latest/", allow_local=False
                )

    def test_multicast_blocked_even_with_allow_local(self):
        """Multicast addresses must be blocked even with allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("224.0.0.1", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url("http://224.0.0.1/", allow_local=True)

    def test_reserved_blocked_even_with_allow_local(self):
        """Reserved ranges (240.0.0.0/4) must be blocked with allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("240.0.0.1", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url("http://240.0.0.1/", allow_local=True)

    def test_broadcast_blocked_even_with_allow_local(self):
        """Broadcast (255.255.255.255) must be blocked with allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("255.255.255.255", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url("http://255.255.255.255/", allow_local=True)

    def test_cgn_blocked_even_with_allow_local(self):
        """CGN shared address space (100.64.0.0/10) must be blocked with allow_local."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("100.64.0.1", 80))],
        ):
            with pytest.raises(SSRFError, match="always blocked"):
                validate_instance_url("http://100.64.0.1/", allow_local=True)


class TestPrivateIPsAllowedWithAllowLocal:
    """Private IPs should pass SSRF validation when allow_local=True."""

    def test_private_ip_allowed_with_allow_local(self):
        """192.168.x.x should pass when allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("192.168.1.1", 8989))],
        ):
            try:
                validate_instance_url("http://192.168.1.1:8989", allow_local=True)
            except SSRFError:
                pytest.fail("Private IP should be allowed with allow_local=True")

    def test_10_network_allowed_with_allow_local(self):
        """10.x.x.x should pass when allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 8989))],
        ):
            try:
                validate_instance_url("http://10.0.0.5:8989", allow_local=True)
            except SSRFError:
                pytest.fail("10.x.x.x should be allowed with allow_local=True")

    def test_172_16_network_allowed_with_allow_local(self):
        """172.16.x.x should pass when allow_local=True."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("172.16.0.1", 8989))],
        ):
            try:
                validate_instance_url("http://172.16.0.1:8989", allow_local=True)
            except SSRFError:
                pytest.fail("172.16.x.x should be allowed with allow_local=True")

    def test_private_ip_blocked_without_allow_local(self):
        """Private IPs must be blocked when allow_local=False."""
        with patch(
            "splintarr.core.ssrf_protection.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("192.168.1.1", 8989))],
        ):
            with pytest.raises(SSRFError, match="Private IPs are not allowed"):
                validate_instance_url("http://192.168.1.1:8989", allow_local=False)
