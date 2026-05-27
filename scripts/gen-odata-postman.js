#!/usr/bin/env node
/**
 * gen-odata-postman.js
 *
 * Generates a Postman Collection v2.1 JSON file for a SAP OData V2 service.
 * The generated collection includes:
 *   1. Fetch CSRF Token (GET) — stores token + cookies as collection variables
 *   2. Get Entity Set (GET with $top=10&$format=json)
 *   3. Create Entity (POST) — uses the payload from assets/payloads/po-create.json
 *   4. Update Entity (PATCH) — skeleton for item-level update
 *
 * Usage:
 *   node gen-odata-postman.js \
 *     --host sap-dev.example.com \
 *     --port 44300 \
 *     --service API_PURCHASEORDER_PROCESS_SRV \
 *     --user APIUSER \
 *     --output po-collection.json
 *
 *   node gen-odata-postman.js --help
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ─── Argument parsing ────────────────────────────────────────────────────────

function parseArgs(argv) {
    const args = {};
    for (let i = 2; i < argv.length; i++) {
        if (argv[i] === '--help' || argv[i] === '-h') {
            printHelp();
            process.exit(0);
        }
        if (argv[i].startsWith('--')) {
            const key = argv[i].slice(2);
            const val = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true';
            args[key] = val;
        }
    }
    return args;
}

function printHelp() {
    console.log(`
gen-odata-postman.js — Generate Postman Collection for SAP OData V2 service

Usage:
  node gen-odata-postman.js [options]

Options:
  --host      SAP server hostname or IP           (required)
  --port      SAP HTTPS port                      (default: 44300)
  --service   OData service technical name        (required)
  --entity    Primary entity set name             (default: auto-detected)
  --user      SAP username for Basic Auth         (default: APIUSER)
  --protocol  http or https                       (default: https)
  --output    Output file path                    (default: <service>.postman_collection.json)
  --help      Show this help

Examples:
  node gen-odata-postman.js \\
    --host sap-dev.example.com \\
    --port 44300 \\
    --service API_PURCHASEORDER_PROCESS_SRV \\
    --user APIUSER \\
    --output po-collection.json

  node gen-odata-postman.js \\
    --host 10.10.1.50 \\
    --port 8000 \\
    --protocol http \\
    --service API_SALES_ORDER_SRV \\
    --entity A_SalesOrder
`);
}

// ─── Default entity set per known service ────────────────────────────────────

const KNOWN_SERVICES = {
    'API_PURCHASEORDER_PROCESS_SRV': {
        entity:      'A_PurchaseOrder',
        entityKey:   "PurchaseOrder='4500012345'",
        itemEntity:  'A_PurchaseOrderItem',
        itemKey:     "PurchaseOrder='4500012345',PurchaseOrderItem='00010'",
        payloadFile: 'assets/payloads/po-create.json',
        updateBody:  '{"OrderQuantity": "15", "OrderQuantityUnit": "EA"}',
        description: 'SAP Purchase Order OData V2 API',
    },
    'API_SALES_ORDER_SRV': {
        entity:      'A_SalesOrder',
        entityKey:   "SalesOrder='0000012345'",
        itemEntity:  'A_SalesOrderItem',
        itemKey:     "SalesOrder='0000012345',SalesOrderItem='000010'",
        payloadFile: null,
        updateBody:  '{"RequestedQuantity": "8", "RequestedQuantityUnit": "EA"}',
        description: 'SAP Sales Order OData V2 API',
    },
    'API_MATERIAL_STOCK_SRV': {
        entity:      'A_MatlStkInAcctMod',
        entityKey:   null,
        itemEntity:  null,
        itemKey:     null,
        payloadFile: null,
        updateBody:  null,
        description: 'SAP Material Stock OData V2 API',
    },
};

// ─── UUID generator ──────────────────────────────────────────────────────────

function uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
}

// ─── Postman Collection builder ──────────────────────────────────────────────

function buildCollection(opts) {
    const {
        host,
        port,
        protocol,
        service,
        entity,
        entityKey,
        itemEntity,
        itemKey,
        user,
        description,
        updateBody,
        payloadContent,
    } = opts;

    const baseUrl = `{{protocol}}://{{host}}:{{port}}/sap/opu/odata/sap/{{service}}`;
    const serviceRoot = `${baseUrl}/`;

    // Pre-request script to fetch CSRF token (runs before POST/PATCH requests)
    const csrfPreRequestScript = [
        '// Fetch CSRF token if not already in collection variables',
        "const token = pm.collectionVariables.get('x_csrf_token');",
        "if (!token || token === 'fetch-on-run') {",
        '    const getRequest = {',
        "        url: pm.collectionVariables.get('service_root'),",
        "        method: 'GET',",
        '        header: {',
        "            'X-CSRF-Token': 'Fetch',",
        "            'Accept': 'application/json',",
        "            'Authorization': 'Basic ' + btoa(",
        "                pm.collectionVariables.get('sap_user') + ':' +",
        "                pm.environment.get('sap_password')",
        '            )',
        '        }',
        '    };',
        '    pm.sendRequest(getRequest, (err, res) => {',
        "        pm.collectionVariables.set('x_csrf_token', res.headers.get('x-csrf-token'));",
        "        const cookies = res.headers.get('set-cookie') || '';",
        "        pm.collectionVariables.set('sap_session_cookie', cookies.split(';')[0]);",
        '    });',
        '}',
    ].join('\n');

    // Tests script for CSRF token extraction (on the Fetch request)
    const csrfTestScript = [
        "const token = pm.response.headers.get('x-csrf-token');",
        'pm.test("CSRF token fetched", () => {',
        '    pm.expect(token).to.be.a("string").and.not.empty;',
        '});',
        "pm.collectionVariables.set('x_csrf_token', token);",
        '',
        '// Store session cookie',
        "const cookieHeader = pm.response.headers.get('set-cookie') || '';",
        "const sessionCookie = cookieHeader.split(',').find(c => c.includes('SAP_SESSIONID')) || cookieHeader;",
        "pm.collectionVariables.set('sap_session_cookie', sessionCookie.split(';')[0].trim());",
        "pm.test('Response status is 200', () => pm.response.to.have.status(200));",
    ].join('\n');

    // Build requests
    const requests = [];

    // 1. Fetch CSRF Token
    requests.push({
        name: '1. Fetch CSRF Token',
        request: {
            method: 'GET',
            header: [
                { key: 'X-CSRF-Token', value: 'Fetch' },
                { key: 'Accept', value: 'application/json' },
            ],
            url: {
                raw:      `${serviceRoot}`,
                protocol: '{{protocol}}',
                host:     ['{{host}}'],
                port:     '{{port}}',
                path:     ['sap', 'opu', 'odata', 'sap', '{{service}}', ''],
            },
            description: [
                'Fetches a CSRF token and session cookie from the service root.',
                'Test script automatically stores the token and cookie as collection variables.',
                'Run this before any POST/PATCH/DELETE request.',
            ].join('\n'),
            auth: {
                type: 'basic',
                basic: [
                    { key: 'username', value: '{{sap_user}}',     type: 'string' },
                    { key: 'password', value: '{{sap_password}}', type: 'string' },
                ],
            },
        },
        event: [
            {
                listen: 'test',
                script: { type: 'text/javascript', exec: csrfTestScript.split('\n') },
            },
        ],
        _postman_id: uuid(),
    });

    // 2. Get Entity Set (list)
    requests.push({
        name: `2. Get ${entity} List`,
        request: {
            method: 'GET',
            header: [
                { key: 'Accept', value: 'application/json' },
            ],
            url: {
                raw:   `${baseUrl}/${entity}?$top=10&$format=json`,
                query: [
                    { key: '$top',    value: '10' },
                    { key: '$format', value: 'json' },
                    { key: '$expand', value: '', disabled: true, description: 'E.g.: to_PurchaseOrderItem' },
                    { key: '$filter', value: '', disabled: true, description: 'E.g.: CompanyCode eq \'1000\'' },
                    { key: '$select', value: '', disabled: true, description: 'E.g.: PurchaseOrder,Supplier,PurchaseOrderDate' },
                ],
            },
            auth: {
                type: 'basic',
                basic: [
                    { key: 'username', value: '{{sap_user}}',     type: 'string' },
                    { key: 'password', value: '{{sap_password}}', type: 'string' },
                ],
            },
            description: `GET ${entity} list with $top=10. Add $filter, $expand, $select as needed.`,
        },
        event: [
            {
                listen: 'test',
                script: {
                    type: 'text/javascript',
                    exec: [
                        "pm.test('Status 200', () => pm.response.to.have.status(200));",
                        "pm.test('Has d.results', () => {",
                        "    const body = pm.response.json();",
                        "    pm.expect(body.d.results).to.be.an('array');",
                        '});',
                    ],
                },
            },
        ],
        _postman_id: uuid(),
    });

    // 3. Create Entity (POST) — only if we have a payload
    if (payloadContent) {
        requests.push({
            name: `3. Create ${entity}`,
            request: {
                method: 'POST',
                header: [
                    { key: 'X-CSRF-Token',  value: '{{x_csrf_token}}' },
                    { key: 'Cookie',        value: '{{sap_session_cookie}}' },
                    { key: 'Content-Type',  value: 'application/json' },
                    { key: 'Accept',        value: 'application/json' },
                ],
                body: {
                    mode: 'raw',
                    raw:     payloadContent,
                    options: { raw: { language: 'json' } },
                },
                url: {
                    raw: `${baseUrl}/${entity}`,
                },
                auth: {
                    type: 'basic',
                    basic: [
                        { key: 'username', value: '{{sap_user}}',     type: 'string' },
                        { key: 'password', value: '{{sap_password}}', type: 'string' },
                    ],
                },
                description: [
                    `POST to ${entity} to create a new document.`,
                    'Requires a valid CSRF token and session cookie from request #1.',
                    'Edit the body with your actual values before running.',
                ].join('\n'),
            },
            event: [
                {
                    listen: 'prerequest',
                    script: { type: 'text/javascript', exec: csrfPreRequestScript.split('\n') },
                },
                {
                    listen: 'test',
                    script: {
                        type: 'text/javascript',
                        exec: [
                            "pm.test('Status 201 Created', () => pm.response.to.have.status(201));",
                            "const body = pm.response.json();",
                            "if (body && body.d) {",
                            "    pm.collectionVariables.set('last_created_key', JSON.stringify(body.d));",
                            "    console.log('Created document:', JSON.stringify(body.d, null, 2));",
                            "}",
                        ],
                    },
                },
            ],
            _postman_id: uuid(),
        });
    }

    // 4. Update Entity (PATCH)
    if (itemEntity && itemKey && updateBody) {
        requests.push({
            name: `4. Update ${itemEntity} (PATCH)`,
            request: {
                method: 'PATCH',
                header: [
                    { key: 'X-CSRF-Token',  value: '{{x_csrf_token}}' },
                    { key: 'Cookie',        value: '{{sap_session_cookie}}' },
                    { key: 'Content-Type',  value: 'application/json' },
                    { key: 'Accept',        value: 'application/json' },
                ],
                body: {
                    mode: 'raw',
                    raw:     updateBody,
                    options: { raw: { language: 'json' } },
                },
                url: {
                    raw: `${baseUrl}/${itemEntity}(${itemKey})`,
                },
                auth: {
                    type: 'basic',
                    basic: [
                        { key: 'username', value: '{{sap_user}}',     type: 'string' },
                        { key: 'password', value: '{{sap_password}}', type: 'string' },
                    ],
                },
                description: [
                    `PATCH to ${itemEntity} to update an existing item.`,
                    `Replace the key fields in the URL: ${itemKey}`,
                    'Requires a valid CSRF token and session cookie from request #1.',
                ].join('\n'),
            },
            event: [
                {
                    listen: 'test',
                    script: {
                        type: 'text/javascript',
                        exec: [
                            "pm.test('Status 204 No Content', () => pm.response.to.have.status(204));",
                        ],
                    },
                },
            ],
            _postman_id: uuid(),
        });
    }

    // Build the collection
    return {
        info: {
            _postman_id: uuid(),
            name:        `SAP OData: ${service}`,
            description: [
                description || `SAP OData V2 service: ${service}`,
                '',
                'Generated by gen-odata-postman.js',
                `Host: ${host}:${port}`,
                '',
                'Setup:',
                '  1. Set environment variable "sap_password" to your SAP user password.',
                '  2. Run request #1 (Fetch CSRF Token) before any write requests.',
                '  3. Update entity key values in PATCH URL before running update requests.',
                '',
                'Collection variables (auto-populated by tests):',
                '  x_csrf_token       — CSRF token for write operations',
                '  sap_session_cookie — SAP session cookie',
            ].join('\n'),
            schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
        },
        variable: [
            { key: 'protocol',          value: protocol,          type: 'string' },
            { key: 'host',              value: host,              type: 'string' },
            { key: 'port',              value: String(port),      type: 'string' },
            { key: 'service',           value: service,           type: 'string' },
            { key: 'sap_user',          value: user,              type: 'string' },
            { key: 'service_root',      value: `${protocol}://${host}:${port}/sap/opu/odata/sap/${service}/`, type: 'string' },
            { key: 'x_csrf_token',      value: 'fetch-on-run',   type: 'string' },
            { key: 'sap_session_cookie', value: '',              type: 'string' },
            { key: 'last_created_key',  value: '',               type: 'string' },
        ],
        item: requests.map((r) => ({
            name:          r.name,
            _postman_id:   r._postman_id,
            protocolProfileBehavior: {},
            request:       r.request,
            response:      [],
            event:         r.event || [],
        })),
    };
}

// ─── Main ─────────────────────────────────────────────────────────────────────

function main() {
    const args = parseArgs(process.argv);

    // Validate required arguments
    if (!args.host)    { console.error('Error: --host is required'); process.exit(1); }
    if (!args.service) { console.error('Error: --service is required'); process.exit(1); }

    const port     = parseInt(args.port || '44300', 10);
    const protocol = args.protocol || 'https';
    const service  = args.service;
    const host     = args.host;
    const user     = args.user || 'APIUSER';
    const output   = args.output || `${service}.postman_collection.json`;

    // Resolve service metadata
    const meta    = KNOWN_SERVICES[service] || {};
    const entity  = args.entity || meta.entity || 'A_Entity';
    const entityKey  = meta.entityKey  || null;
    const itemEntity = meta.itemEntity || null;
    const itemKey    = meta.itemKey    || null;
    const updateBody = meta.updateBody || '{"Field": "NewValue"}';
    const description = meta.description || `SAP OData V2 service: ${service}`;

    // Load payload if available
    let payloadContent = null;
    if (meta.payloadFile) {
        const payloadPath = path.resolve(meta.payloadFile);
        if (fs.existsSync(payloadPath)) {
            payloadContent = fs.readFileSync(payloadPath, 'utf8');
        } else {
            console.warn(`Warning: Payload file not found at ${payloadPath}; POST request will have empty body`);
            payloadContent = '{}';
        }
    }

    const collection = buildCollection({
        host, port, protocol, service, entity, entityKey,
        itemEntity, itemKey, user, description, updateBody, payloadContent,
    });

    const outputPath = path.resolve(output);
    fs.writeFileSync(outputPath, JSON.stringify(collection, null, 2), 'utf8');

    console.log(`\nPostman Collection generated successfully:`);
    console.log(`  File:    ${outputPath}`);
    console.log(`  Service: ${service}`);
    console.log(`  Host:    ${protocol}://${host}:${port}`);
    console.log(`  Entity:  ${entity}`);
    console.log(`\nRequests in collection:`);
    collection.item.forEach((item, i) => console.log(`  ${item.name}`));
    console.log(`\nImport into Postman: File → Import → ${outputPath}`);
    console.log(`Set environment variable 'sap_password' before running.\n`);
}

main();
