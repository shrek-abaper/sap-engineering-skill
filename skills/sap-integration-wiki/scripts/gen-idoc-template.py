#!/usr/bin/env python3
"""
gen-idoc-template.py

Generates a skeleton IDoc XML file for a given SAP IDoc message type.
The generated XML contains:
  - EDI_DC40 control record with all mandatory fields (labeled placeholders)
  - Key data segments for the specified IDoc type
  - XML comments on each field explaining what it means

Supported message types:
  ORDERS    — Purchase/Sales Order (ORDERS05)
  ORDRSP    — Order Response (ORDERS05)
  DESADV    — Despatch Advice / Advance Ship Notice (DESADV01)
  INVOIC    — Invoice (INVOIC02)

Usage:
    python gen-idoc-template.py \
        --msgtype ORDERS \
        --idoctype ORDERS05 \
        --sender-partner EXTERNAL_SYS \
        --receiver-partner SAP_PROD \
        --output orders05-skeleton.xml

    python gen-idoc-template.py --help
"""

import argparse
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Segment definitions (key segments per IDoc type)
# ---------------------------------------------------------------------------

SEGMENTS = {
    'ORDERS05': {
        'description': 'Purchase/Sales Order IDoc (ORDERS message type)',
        'segments': [
            {
                'name': 'E1EDK01',
                'description': 'Order header: document type, dates, basic control data',
                'fields': [
                    ('CURCY',   'USD',        'Document currency (ISO code)'),
                    ('HWAER',   'USD',        'Local/house currency (usually same as CURCY)'),
                    ('WKURS',   '1.00000',    'Exchange rate (1.0 if same currency)'),
                    ('ZTERM',   'NET30',      'Terms of payment key (from SAP payment terms config)'),
                    ('BSART',   'NB',         'Document type: NB=Standard PO, ZNB=Custom PO'),
                    ('BELNR',   '4500012345', 'SAP document number (PO number)'),
                    ('NTGEW',   '10.000',     'Net weight of the entire document'),
                    ('BRGEW',   '11.500',     'Gross weight of the entire document'),
                    ('GEWEI',   'KG',         'Weight unit (KG, LB, etc.)'),
                    ('FKTYP',   '',           'Billing type (leave blank for PO)'),
                    ('ABLAD',   '',           'Unloading point at the ship-to address'),
                    ('BSTZD',   '',           'Customer order number identifier'),
                ],
            },
            {
                'name': 'E1EDK14',
                'description': 'Organizational data: purchasing organization, company code, sales organization',
                'fields': [
                    ('ORGID', '1000', 'Organization identifier (purchasing org, company code, etc.)'),
                    ('QUALF', '006',  'Qualifier: 006=purchasing org, 007=company code, 008=sales org, 012=plant'),
                ],
                'multiple': True,
                'instances': [
                    [('ORGID', '1000', 'Purchasing organization'), ('QUALF', '006', 'Qualifier: 006 = Purchasing Org')],
                    [('ORGID', '1000', 'Company code'),            ('QUALF', '007', 'Qualifier: 007 = Company Code')],
                    [('ORGID', '001',  'Purchasing group'),        ('QUALF', '011', 'Qualifier: 011 = Purchasing Group')],
                ],
            },
            {
                'name': 'E1EDKA1',
                'description': 'Partner identifiers (sold-to, ship-to, vendor, etc.)',
                'fields': [
                    ('PARVW',  'LF', 'Partner function: LF=Vendor, AG=Sold-to, WE=Ship-to, RE=Invoice-to'),
                    ('PARTN',  '1000001', 'Partner number (vendor account, customer account)'),
                    ('LIFNR',  '1000001', 'Vendor account number'),
                    ('KUKDNR', '',        'Customer number at partner (if known)'),
                    ('ADRNR',  '',        'Address number from SAP address management'),
                    ('NAME1',  'ACME Corp',  'Partner name line 1'),
                    ('STRAS',  '123 Main St', 'Street address'),
                    ('ORT01',  'San Francisco', 'City'),
                    ('PSTLZ',  '94105',      'Postal code'),
                    ('LAND1',  'US',         'Country code (ISO 2-letter)'),
                ],
                'multiple': True,
                'instances': [
                    [('PARVW', 'LF', 'Vendor'), ('PARTN', '1000001', 'Vendor account in SAP')],
                    [('PARVW', 'WE', 'Ship-to'), ('PARTN', '1000001', 'Ship-to party')],
                ],
            },
            {
                'name': 'E1EDP01',
                'description': 'Order item: material, quantity, price, units',
                'fields': [
                    ('POSEX',  '000010',    'Item number (6 digits, zero-padded)'),
                    ('ACTION', '000',       'Change indicator: 000=new, 001=change, 002=delete, 003=no action'),
                    ('PSTYP',  '0',         'Item category: 0=standard, 2=blanket PO, D=service, L=subcontracting'),
                    ('MENGE',  '10.000',    'Order quantity'),
                    ('MENEE',  'EA',        'Unit of measure (EA=each, KG=kilogram, PC=piece)'),
                    ('BMNG2',  '10.000',    'Order quantity in ordering unit (usually same as MENGE)'),
                    ('PMENE',  'EA',        'Ordering unit'),
                    ('ABFTZ',  '',          'Weeks supply time (optional)'),
                    ('VPREI',  '25.00',     'Price per quantity unit (net price)'),
                    ('PEINH',  '1',         'Price unit (e.g. 1 = price per 1 EA, 100 = price per 100)'),
                    ('NETWR',  '250.00',    'Net value of the item (MENGE * VPREI / PEINH)'),
                    ('ANETW',  '250.00',    'Net value in document currency'),
                    ('SKFBP',  '250.00',    'Amount qualifying for cash discount'),
                    ('CURCY',  'USD',       'Item currency (usually same as header currency)'),
                    ('PREIS',  '25.00',     'Item price (alternative to VPREI in some IDoc versions)'),
                ],
            },
            {
                'name': 'E1EDP19',
                'description': 'Material/article identification per item',
                'fields': [
                    ('QUALF',  '001',       'Qualifier: 001=buyer material number, 002=vendor material number, 007=EAN/barcode'),
                    ('IDTNR',  'RAW-001',   'Material/article identifier number'),
                    ('KTEXT',  'Raw material 001', 'Short description text'),
                    ('MFRPN',  '',          'Manufacturer part number (if QUALF=012)'),
                    ('MFRNR',  '',          'Manufacturer number in SAP'),
                ],
            },
            {
                'name': 'E1EDP04',
                'description': 'Schedule line / delivery date per item',
                'fields': [
                    ('QUALF',  '001',       'Qualifier: 001=delivery date, 002=production start date'),
                    ('BEDAT',  '20260530',  'Date (YYYYMMDD format)'),
                    ('NTGEW',  '10.000',    'Net weight for this schedule line'),
                    ('GEWEI',  'KG',        'Weight unit'),
                    ('MENGE',  '10.000',    'Quantity for this delivery date'),
                    ('MENEE',  'EA',        'Unit of measure'),
                ],
            },
            {
                'name': 'E1EDS01',
                'description': 'Document summary / trailer segment',
                'fields': [
                    ('SUMID',  '001',       'Summary qualifier: 001=number of items'),
                    ('SUMME',  '1',         'Summary value (e.g. total number of items)'),
                    ('SUNIT',  '',          'Summary unit'),
                    ('WAERQ',  'USD',       'Currency for monetary summary'),
                ],
            },
        ],
    },
    'DESADV01': {
        'description': 'Despatch Advice (Advance Ship Notice) IDoc',
        'segments': [
            {
                'name': 'E1EDL20',
                'description': 'Delivery header data',
                'fields': [
                    ('VBELN', '0080012345', 'Delivery number'),
                    ('VSTEL', '1000',       'Shipping point'),
                    ('LGORT', '0001',       'Storage location'),
                    ('WERKS', '1000',       'Plant'),
                    ('NTGEW', '50.000',     'Net weight of delivery'),
                    ('BRGEW', '55.000',     'Gross weight of delivery'),
                    ('GEWEI', 'KG',         'Weight unit'),
                    ('BOLNR', 'BOL-001',    'Bill of lading number'),
                ],
            },
            {
                'name': 'E1EDL24',
                'description': 'Delivery item data',
                'fields': [
                    ('POSNR', '000010', 'Delivery item number'),
                    ('MATNR', 'FG-001', 'Material number'),
                    ('ARKTX', 'Finished goods 001', 'Item description'),
                    ('MENGE', '5.000',  'Delivered quantity'),
                    ('VRKME', 'EA',     'Sales unit of measure'),
                    ('WERKS', '1000',   'Plant'),
                    ('LGORT', '0001',   'Storage location'),
                ],
            },
        ],
    },
    'INVOIC02': {
        'description': 'Invoice IDoc (INVOIC message type)',
        'segments': [
            {
                'name': 'E1EDK01',
                'description': 'Invoice header',
                'fields': [
                    ('CURCY', 'USD',     'Invoice currency'),
                    ('BSART', 'RE',      'Document type: RE=vendor invoice, ZRE=custom'),
                    ('BELNR', 'INV-001', 'Invoice document number from vendor'),
                    ('NTGEW', '',        'Net weight (optional for invoices)'),
                ],
            },
            {
                'name': 'E1EDP01',
                'description': 'Invoice item',
                'fields': [
                    ('POSEX', '000010', 'Item number'),
                    ('MENGE', '10.000', 'Invoiced quantity'),
                    ('MENEE', 'EA',     'Unit of measure'),
                    ('VPREI', '25.00',  'Price per unit'),
                    ('NETWR', '250.00', 'Net value'),
                    ('CURCY', 'USD',    'Currency'),
                ],
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------

def indent(level):
    return '    ' * level


def generate_control_record(args, direction):
    """Generate the EDI_DC40 control record."""
    timestamp = datetime.now().strftime('%Y%m%d')
    time_str  = datetime.now().strftime('%H%M%S')
    idoc_num  = '0000000000000001'

    lines = []
    lines.append(f'{indent(1)}<EDI_DC40 SEGMENT="1">')
    lines.append(f'{indent(2)}<!-- ============================================================ -->')
    lines.append(f'{indent(2)}<!-- EDI_DC40: IDoc Control Record                               -->')
    lines.append(f'{indent(2)}<!-- This is mandatory and must be the first record in every IDoc -->')
    lines.append(f'{indent(2)}<!-- ============================================================ -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- Document number: 16-digit, zero-padded. SAP assigns on import. Use placeholder for outbound. -->')
    lines.append(f'{indent(2)}<TABNAM>EDI_DC40</TABNAM>   <!-- Always "EDI_DC40" for V4 control records -->')
    lines.append(f'{indent(2)}<MANDT>100</MANDT>           <!-- SAP client number (e.g. 100, 800) -->')
    lines.append(f'{indent(2)}<DOCNUM>{idoc_num}</DOCNUM>  <!-- IDoc document number: SAP assigns on inbound; set to 0s for new outbound IDocs -->')
    lines.append(f'{indent(2)}<DOCREL>756</DOCREL>         <!-- SAP release that created this IDoc (e.g. 756 = S/4HANA 2023) -->')
    lines.append(f'{indent(2)}<STATUS>03</STATUS>          <!-- Initial status: 03=sent (outbound), 30=ready for inbound processing -->')
    lines.append(f'{indent(2)}<DIRECT>{direction}</DIRECT> <!-- Direction: 1=outbound (SAP→external), 2=inbound (external→SAP) -->')
    lines.append(f'{indent(2)}<OUTMOD>1</OUTMOD>           <!-- Output mode: 1=immediate send, 2=collect, 4=no further processing -->')
    lines.append(f'{indent(2)}<EXPRSS></EXPRSS>            <!-- Express flag: X=override partner profile, blank=use profile -->')
    lines.append(f'{indent(2)}<TEST></TEST>                <!-- Test flag: T=test run (no posting), blank=productive -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- Message type: the logical name for this type of business document -->')
    lines.append(f'{indent(2)}<MESTYP>{args.msgtype}</MESTYP>  <!-- Message type (e.g. ORDERS, ORDRSP, DESADV, INVOIC) -->')
    lines.append(f'{indent(2)}<MESCOD></MESCOD>            <!-- Message code (optional, e.g. for subtype distinction) -->')
    lines.append(f'{indent(2)}<MESFCT></MESFCT>            <!-- Message function (optional) -->')
    lines.append(f'{indent(2)}<STD>UN</STD>                <!-- EDI standard: UN=UN/EDIFACT, AN=ANSI X12 -->')
    lines.append(f'{indent(2)}<STDVRS>D96A</STDVRS>        <!-- EDI standard version (e.g. D96A = EDIFACT release 1996A) -->')
    lines.append(f'{indent(2)}<STDMES>{args.msgtype}</STDMES> <!-- Standard message type (same as MESTYP usually) -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- Sender identification -->')
    lines.append(f'{indent(2)}<SNDPOR>SAPECC</SNDPOR>     <!-- Sending port name (defined in WE21, e.g. the SAP system port) -->')
    lines.append(f'{indent(2)}<SNDPRT>LS</SNDPRT>         <!-- Sending partner type: LS=Logical System, LI=Vendor, KU=Customer -->')
    lines.append(f'{indent(2)}<SNDPFC></SNDPFC>           <!-- Sending partner function (usually empty) -->')
    lines.append(f'{indent(2)}<SNDPRN>{args.sender_partner}</SNDPRN> <!-- Sending partner number: logical system name or vendor/customer account -->')
    lines.append(f'{indent(2)}<SNDSAD></SNDSAD>           <!-- Sender address (optional) -->')
    lines.append(f'{indent(2)}<SNDLAD></SNDLAD>           <!-- Sender logical address (optional) -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- Receiver identification -->')
    lines.append(f'{indent(2)}<RCVPOR>PARTNERPORT</RCVPOR> <!-- Receiving port (defined in WE21 for the partner system) -->')
    lines.append(f'{indent(2)}<RCVPRT>LI</RCVPRT>         <!-- Receiving partner type: LI=Vendor, KU=Customer, LS=Logical System -->')
    lines.append(f'{indent(2)}<RCVPFC></RCVPFC>           <!-- Receiving partner function -->')
    lines.append(f'{indent(2)}<RCVPRN>{args.receiver_partner}</RCVPRN> <!-- Receiving partner number: must match partner profile in WE20 -->')
    lines.append(f'{indent(2)}<RCVSAD></RCVSAD>           <!-- Receiver address (optional) -->')
    lines.append(f'{indent(2)}<RCVLAD></RCVLAD>           <!-- Receiver logical address (optional) -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- Timestamp -->')
    lines.append(f'{indent(2)}<CREDAT>{timestamp}</CREDAT> <!-- Creation date (YYYYMMDD) -->')
    lines.append(f'{indent(2)}<CRETIM>{time_str}</CRETIM>  <!-- Creation time (HHMMSS) -->')
    lines.append(f'{indent(2)}<SERIAL></SERIAL>            <!-- Serialization field (optional; blank = no ordering constraint) -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(2)}<!-- IDoc type -->')
    lines.append(f'{indent(2)}<IDOCTYP>{args.idoctype}</IDOCTYP> <!-- IDoc basic type (e.g. ORDERS05, DESADV01). Must match WE20 partner profile. -->')
    lines.append(f'{indent(2)}<CIMTYP></CIMTYP>           <!-- IDoc extension type (e.g. ZORDERS05E for custom segments). Leave blank if not extended. -->')
    lines.append(f'{indent(2)}')

    lines.append(f'{indent(1)}</EDI_DC40>')
    return lines


def generate_segment(seg_def, instance_fields=None, instance_num=1):
    """Generate one IDoc data segment."""
    name = seg_def['name']
    description = seg_def['description']
    fields = instance_fields if instance_fields else seg_def.get('fields', [])

    lines = []
    lines.append(f'{indent(1)}')
    lines.append(f'{indent(1)}<!-- ── {name}: {description} ── -->')
    lines.append(f'{indent(1)}<{name} SEGMENT="{instance_num}">')
    for field_name, field_value, field_comment in fields:
        lines.append(f'{indent(2)}<{field_name}>{field_value}</{field_name}>  <!-- {field_comment} -->')
    lines.append(f'{indent(1)}<!-- Note: SDATA in raw IDoc files is a fixed 1000-byte field;')
    lines.append(f'{indent(1)}          in XML IDoc format, each field is a separate element. -->')
    lines.append(f'{indent(1)}')
    lines.append(f'{indent(1)}</{name}>')
    return lines


def generate_idoc_xml(args):
    """Generate the complete IDoc XML document."""
    idoc_def = SEGMENTS.get(args.idoctype)
    if not idoc_def:
        print(f"Warning: IDoc type '{args.idoctype}' not in built-in templates. "
              f"Generating minimal EDI_DC40 only.", file=sys.stderr)
        idoc_def = {'description': f'Custom IDoc type {args.idoctype}', 'segments': []}

    # Direction: outbound from SAP (1) or inbound to SAP (2)
    direction = '2' if args.inbound else '1'

    xml_lines = []
    xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_lines.append(f'<!--')
    xml_lines.append(f'  IDoc XML Template')
    xml_lines.append(f'  Message Type: {args.msgtype}')
    xml_lines.append(f'  IDoc Type:    {args.idoctype}')
    xml_lines.append(f'  Direction:    {"Inbound (external→SAP)" if args.inbound else "Outbound (SAP→external)"}')
    xml_lines.append(f'  Sender:       {args.sender_partner}')
    xml_lines.append(f'  Receiver:     {args.receiver_partner}')
    xml_lines.append(f'  Generated:    {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    xml_lines.append(f'  Generator:    gen-idoc-template.py')
    xml_lines.append(f'')
    xml_lines.append(f'  USAGE:')
    xml_lines.append(f'    1. Replace all placeholder values (in CAPS or with description comments) with real data.')
    xml_lines.append(f'    2. Remove the XML comments before sending to SAP (they are for guidance only).')
    xml_lines.append(f'    3. Ensure your partner profile (WE20) is configured for {args.receiver_partner} / {args.msgtype}.')
    xml_lines.append(f'    4. Post inbound IDoc via RFC function IDOC_INBOUND_ASYNCHRONOUS or WE19 for testing.')
    xml_lines.append(f'-->')
    xml_lines.append(f'')
    xml_lines.append(f'<IDOC BEGIN="1">')

    # Control record
    xml_lines.extend(generate_control_record(args, direction))

    # Data segments
    for seg_def in idoc_def.get('segments', []):
        if seg_def.get('multiple') and seg_def.get('instances'):
            for i, instance_fields in enumerate(seg_def['instances'], 1):
                xml_lines.extend(generate_segment(seg_def, instance_fields=instance_fields, instance_num=i))
        else:
            xml_lines.extend(generate_segment(seg_def))

    xml_lines.append('')
    xml_lines.append('</IDOC>')

    return '\n'.join(xml_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate SAP IDoc XML skeleton",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported IDoc types:
  ORDERS05   — Purchase Order / Sales Order
  DESADV01   — Despatch Advice (Advance Ship Notice)
  INVOIC02   — Invoice

Examples:
  python gen-idoc-template.py \\
    --msgtype ORDERS --idoctype ORDERS05 \\
    --sender-partner EXTERNAL_SYS --receiver-partner SAP_PROD \\
    --output orders05-skeleton.xml

  python gen-idoc-template.py \\
    --msgtype ORDRSP --idoctype ORDERS05 \\
    --sender-partner SUPPLIER001 --receiver-partner SAP_PROD \\
    --inbound \\
    --output ordrsp-inbound.xml
        """
    )

    parser.add_argument('--msgtype',          required=True,
                        help='IDoc message type (e.g. ORDERS, ORDRSP, DESADV, INVOIC)')
    parser.add_argument('--idoctype',         required=True,
                        help='IDoc basic type (e.g. ORDERS05, DESADV01, INVOIC02)')
    parser.add_argument('--sender-partner',   required=True, dest='sender_partner',
                        help='Sending partner number (logical system name or vendor/customer account)')
    parser.add_argument('--receiver-partner', required=True, dest='receiver_partner',
                        help='Receiving partner number (must match WE20 partner profile)')
    parser.add_argument('--inbound',          action='store_true',
                        help='Generate inbound IDoc (direction=2). Default: outbound (direction=1)')
    parser.add_argument('--output',           help='Output XML file path (default: <idoctype>-skeleton.xml)')

    args = parser.parse_args()

    output_path = args.output or f"{args.idoctype.lower()}-skeleton.xml"
    xml_content = generate_idoc_xml(args)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    idoc_def = SEGMENTS.get(args.idoctype, {})
    print(f"\nIDoc XML template generated:")
    print(f"  File:      {os.path.abspath(output_path)}")
    print(f"  Message:   {args.msgtype}")
    print(f"  IDoc type: {args.idoctype}")
    if idoc_def:
        print(f"  Type desc: {idoc_def.get('description', '')}")
        print(f"  Segments:  {', '.join(s['name'] for s in idoc_def.get('segments', []))}")
    print(f"  Direction: {'Inbound' if args.inbound else 'Outbound'}")
    print(f"\nNext steps:")
    print(f"  1. Replace all placeholder values in {output_path}")
    print(f"  2. Verify partner profile in SAP WE20 for '{args.receiver_partner}'")
    print(f"  3. Test with SAP transaction WE19 (IDoc test tool)\n")


if __name__ == '__main__':
    main()
