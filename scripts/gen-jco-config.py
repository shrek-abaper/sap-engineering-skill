#!/usr/bin/env python3
"""
gen-jco-config.py

Generates a SAP JCo .jcoDestination properties file.
Supports both direct connection and load balancing modes.
Each generated property includes a comment explaining its purpose.

Usage:
    python gen-jco-config.py \
        --name SAP_ERP \
        --host sap-erp.example.com \
        --sysnr 00 \
        --client 100 \
        --user JCOUSER \
        --mode direct \
        --output SAP_ERP.jcoDestination

    python gen-jco-config.py \
        --name SAP_ERP_LB \
        --mshost sap-ms.example.com \
        --sysid PRD \
        --group PUBLIC \
        --client 100 \
        --user JCOUSER \
        --mode loadbalance \
        --output SAP_ERP_LB.jcoDestination

    python gen-jco-config.py --help

Notes:
    - Password is not written to the file for security.
      It must be provided at runtime via the JCo API or environment variable.
    - Place the output file in your Java application's working directory,
      or register the destination programmatically.
"""

import argparse
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

def build_direct_connection(args):
    """Build properties for a direct SAP application server connection."""
    lines = []
    lines.append(f"# JCo Destination: {args.name}")
    lines.append(f"# Mode: Direct connection to SAP application server")
    lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Generator: gen-jco-config.py")
    lines.append("")

    lines.append("# ==========================================================")
    lines.append("# SECTION 1: Connection Parameters (required)")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# Application server hostname or IP address."
        " Do not include http:// prefix."
    )
    lines.append(f"jco.client.ashost={args.host}")
    lines.append("")

    lines.append(
        "# SAP system number — a 2-digit number identifying the SAP instance."
        " Usually 00 or 01."
        " Port = 33<SYSNR> (e.g. 3300 for system number 00)."
    )
    lines.append(f"jco.client.sysnr={args.sysnr}")
    lines.append("")

    lines.append(
        "# SAP client number — identifies the business tenant within the SAP system."
        " 3 digits, zero-padded (e.g. 100, 800)."
    )
    lines.append(f"jco.client.client={args.client}")
    lines.append("")

    lines.append("# ==========================================================")
    lines.append("# SECTION 2: Logon Parameters (required)")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# SAP logon user. Use a Communication-type user (not Dialog) to avoid"
        " password expiry issues in automated integrations."
    )
    lines.append(f"jco.client.user={args.user}")
    lines.append("")

    lines.append(
        "# SAP logon password. It is strongly recommended NOT to store the password"
        " in this file in production. Instead, provide it programmatically via"
        " DestinationDataProvider. If you must store it here, restrict file permissions"
        " to the application user only (chmod 600)."
    )
    lines.append(f"# jco.client.passwd=<YOUR_PASSWORD_HERE>")
    lines.append(f"# Uncomment and fill in for testing only:")
    lines.append(f"jco.client.passwd=")
    lines.append("")

    lines.append(
        "# SAP logon language. EN = English, DE = German, ZH = Chinese, etc."
        " Controls the language of error messages returned from SAP."
    )
    lines.append(f"jco.client.lang={args.lang}")
    lines.append("")

    return lines


def build_loadbalance_connection(args):
    """Build properties for a SAP message server (load balancing) connection."""
    lines = []
    lines.append(f"# JCo Destination: {args.name}")
    lines.append(f"# Mode: Load balancing via SAP Message Server")
    lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Generator: gen-jco-config.py")
    lines.append("")

    lines.append("# ==========================================================")
    lines.append("# SECTION 1: Message Server Parameters (load balancing)")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# SAP Message Server hostname or IP."
        " The message server routes connections to available application servers."
    )
    lines.append(f"jco.client.mshost={args.mshost}")
    lines.append("")

    lines.append(
        "# Message server port. Default is 3600 for standard systems,"
        " or 36<instance_nr> for specific instances."
        " Confirm with SAP Basis if unsure."
    )
    lines.append(f"jco.client.msserv={args.msport}")
    lines.append("")

    lines.append(
        "# SAP System ID (SID) — 3-character identifier for the SAP system (e.g. PRD, QAS, DEV)."
        " Required for message server connections."
    )
    lines.append(f"jco.client.r3name={args.sysid}")
    lines.append("")

    lines.append(
        "# SAP logon group — distributes load among application servers in this group."
        " Default group is PUBLIC. Check transaction SMLG in SAP for available groups."
    )
    lines.append(f"jco.client.group={args.group}")
    lines.append("")

    lines.append("# ==========================================================")
    lines.append("# SECTION 2: Logon Parameters (required)")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(f"jco.client.client={args.client}")
    lines.append(f"jco.client.user={args.user}")
    lines.append(f"# jco.client.passwd=<YOUR_PASSWORD_HERE>")
    lines.append(f"jco.client.passwd=")
    lines.append(f"jco.client.lang={args.lang}")
    lines.append("")

    return lines


def build_pool_section(args):
    """Build connection pool configuration properties."""
    lines = []
    lines.append("# ==========================================================")
    lines.append("# SECTION 3: Connection Pool Configuration")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# Maximum number of idle connections kept in the pool."
        " Idle connections are immediately available for new requests without"
        " the overhead of creating a new RFC connection."
        " Rule of thumb: set to the number of concurrent threads that will call SAP."
    )
    lines.append(f"jco.destination.pool_capacity={args.pool_capacity}")
    lines.append("")

    lines.append(
        "# Maximum number of active (in-use) connections allowed at any time."
        " This is the hard limit. Requests beyond this limit wait up to"
        " max_get_client_time before receiving a 'JCO_ERROR_RESOURCE' exception."
        " IMPORTANT: Do not exceed the number of SAP Dialog work processes (SM50)."
    )
    lines.append(f"jco.destination.peak_limit={args.peak_limit}")
    lines.append("")

    lines.append(
        "# Time in milliseconds after which an idle connection is removed from the pool."
        " Prevents keeping connections open when SAP is not in use."
        " Default: 60000 (60 seconds)."
    )
    lines.append(f"jco.destination.expiration_time={args.expiration_time}")
    lines.append("")

    lines.append(
        "# How frequently (in milliseconds) the pool checks for expired idle connections."
        " Should be equal to or less than expiration_time."
    )
    lines.append(f"jco.destination.expiration_check_period={args.expiration_check_period}")
    lines.append("")

    lines.append(
        "# Maximum time in milliseconds a thread waits for an available connection"
        " when pool_capacity and peak_limit are both exhausted."
        " After this time, JCoException with code JCO_ERROR_RESOURCE is thrown."
        " Default: 30000 (30 seconds)."
    )
    lines.append(f"jco.destination.max_get_client_time={args.max_get_client_time}")
    lines.append("")

    return lines


def build_trace_section(args):
    """Build optional trace/debug configuration."""
    lines = []
    lines.append("# ==========================================================")
    lines.append("# SECTION 4: Trace and Debug (optional, disable in production)")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# JCo trace level. 0 = off, 1 = errors only, 2 = errors+warnings, 8 = full."
        " Full trace (8) generates very large log files. Use only for debugging."
    )
    lines.append(f"# jco.client.trace={args.trace}")
    lines.append("")

    lines.append(
        "# RFC trace — enables CPIC-level tracing (very verbose)."
        " Creates files dev_rfc*.trc in the working directory."
        " 0 = off, 1 = on."
    )
    lines.append("# jco.destination.repository_roundtrip_optimization=1")
    lines.append("")

    lines.append(
        "# Destination repository: how long to cache function module metadata (seconds)."
        " -1 = cache indefinitely (recommended for production)."
        "  0 = no caching (re-fetch from SAP on each call — never use in production)."
    )
    lines.append("# jco.destination.repository_dest=")
    lines.append("")

    return lines


def build_ssl_section():
    """Build optional SSL/SNC configuration."""
    lines = []
    lines.append("# ==========================================================")
    lines.append("# SECTION 5: SSL / SNC (Secure Network Communications) — optional")
    lines.append("# ==========================================================")
    lines.append("")

    lines.append(
        "# Enable SNC for encrypted and authenticated RFC connections."
        " 0 = disabled, 1 = enabled."
    )
    lines.append("# jco.client.snc_mode=0")
    lines.append("")

    lines.append(
        "# SNC partner name — the Distinguished Name (DN) of the SAP system's SNC certificate."
        " Example: p:CN=PRD, O=MyCompany, C=DE"
        " Get the correct value from your SAP Basis team (transaction STRUST)."
    )
    lines.append("# jco.client.snc_partnername=p:CN=SID, O=Corp, C=DE")
    lines.append("")

    lines.append(
        "# Path to the SAP Crypto Library (sapcrypto.dll / libsapcrypto.so)."
        " Required when SNC is enabled."
    )
    lines.append("# jco.client.snc_lib=/path/to/sapcrypto.so")
    lines.append("")

    lines.append(
        "# SNC quality of protection level:"
        "  1 = Authentication only"
        "  2 = Integrity protection"
        "  3 = Privacy (encryption) — recommended"
        "  9 = Maximum available"
    )
    lines.append("# jco.client.snc_qop=3")
    lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate SAP JCo .jcoDestination properties file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Direct connection:
    python gen-jco-config.py \\
      --name SAP_ERP --host sap-erp.example.com --sysnr 00 \\
      --client 100 --user JCOUSER --output SAP_ERP.jcoDestination

  Load balancing:
    python gen-jco-config.py \\
      --name SAP_ERP_LB --mode loadbalance \\
      --mshost sap-ms.example.com --sysid PRD --group PUBLIC \\
      --client 100 --user JCOUSER --output SAP_ERP_LB.jcoDestination
        """
    )

    parser.add_argument('--name',    required=True, help='Destination name (used as filename and in Java code)')
    parser.add_argument('--mode',    choices=['direct', 'loadbalance'], default='direct',
                        help='Connection mode: direct (default) or loadbalance')
    # Direct connection params
    parser.add_argument('--host',    help='Application server hostname (direct mode)')
    parser.add_argument('--sysnr',   default='00', help='System number, 2 digits (default: 00)')
    # Load balancing params
    parser.add_argument('--mshost',  help='Message server hostname (load balance mode)')
    parser.add_argument('--msport',  default='3600', help='Message server port (default: 3600)')
    parser.add_argument('--sysid',   help='SAP System ID / SID (load balance mode)')
    parser.add_argument('--group',   default='PUBLIC', help='Logon group (default: PUBLIC)')
    # Common params
    parser.add_argument('--client',  default='100', help='SAP client number (default: 100)')
    parser.add_argument('--user',    default='JCOUSER', help='SAP logon user (default: JCOUSER)')
    parser.add_argument('--lang',    default='EN', help='Logon language (default: EN)')
    # Pool params
    parser.add_argument('--pool-capacity',          default='5',     dest='pool_capacity')
    parser.add_argument('--peak-limit',             default='10',    dest='peak_limit')
    parser.add_argument('--expiration-time',        default='60000', dest='expiration_time')
    parser.add_argument('--expiration-check-period',default='60000', dest='expiration_check_period')
    parser.add_argument('--max-get-client-time',    default='30000', dest='max_get_client_time')
    # Trace
    parser.add_argument('--trace',   default='0', help='Trace level: 0=off, 1=errors, 2=warnings, 8=full')
    # Output
    parser.add_argument('--output',  help='Output file path (default: <name>.jcoDestination)')

    args = parser.parse_args()

    # Validate mode-specific required args
    if args.mode == 'direct' and not args.host:
        parser.error("--host is required for direct connection mode")
    if args.mode == 'loadbalance' and not args.mshost:
        parser.error("--mshost is required for load balance mode")
    if args.mode == 'loadbalance' and not args.sysid:
        parser.error("--sysid is required for load balance mode")

    # Build content
    all_lines = []

    if args.mode == 'direct':
        all_lines.extend(build_direct_connection(args))
    else:
        all_lines.extend(build_loadbalance_connection(args))

    all_lines.extend(build_pool_section(args))
    all_lines.extend(build_trace_section(args))
    all_lines.extend(build_ssl_section())

    # Add Java usage example at end
    all_lines.append("# ==========================================================")
    all_lines.append("# USAGE IN JAVA")
    all_lines.append("# ==========================================================")
    all_lines.append("#")
    all_lines.append(f"# Place this file in your application's working directory as:")
    all_lines.append(f"#   {args.name}.jcoDestination")
    all_lines.append("#")
    all_lines.append("# Then in Java:")
    all_lines.append("#   JCoDestination dest = JCoDestinationManager.getDestination(\"" + args.name + "\");")
    all_lines.append("#   JCoFunction bapi = dest.getRepository().getFunction(\"BAPI_PO_CREATE1\");")
    all_lines.append("#   bapi.execute(dest);")
    all_lines.append("#")
    all_lines.append("# Note: JCo auto-discovers .jcoDestination files in the working directory.")
    all_lines.append("# Alternatively, register destinations programmatically via DestinationDataProvider.")
    all_lines.append("")

    content = "\n".join(all_lines)

    # Write output
    output_path = args.output or f"{args.name}.jcoDestination"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\nJCo destination file generated:")
    print(f"  File:    {os.path.abspath(output_path)}")
    print(f"  Name:    {args.name}")
    print(f"  Mode:    {args.mode}")
    if args.mode == 'direct':
        print(f"  Host:    {args.host}:{args.sysnr}")
    else:
        print(f"  MServer: {args.mshost}:{args.msport} (SID: {args.sysid}, Group: {args.group})")
    print(f"  Client:  {args.client}")
    print(f"  User:    {args.user}")
    print(f"\nIMPORTANT: Edit the file and set jco.client.passwd before use.")
    print(f"           Never commit the file with a real password to version control.\n")


if __name__ == '__main__':
    main()
