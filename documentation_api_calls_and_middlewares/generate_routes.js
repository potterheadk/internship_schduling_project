#!/usr/bin/env node
/**
 * generate_routes.js
 *
 * Scans NestJS backend and Angular frontend to produce a manifest of implemented and used HTTP endpoints.
 * Usage:
 *   node generate_routes.js --backend <backend_path> --frontend <frontend_path>
 *   or simply:
 *   node generate_routes.js
 *
 * Outputs:
 *   output/routes.json
 *   output/routes.md
 *   output/curl_samples.sh
 *   output/fetch_responses.sh
 *   output/README.md
 */

const fs = require('fs');
const path = require('path');
const glob = require('glob');

const BACKEND_DEFAULT = 'nest_docente';
const FRONTEND_DEFAULT = 'Gestion_Docentes_New-main';
const OUTPUT_DIR = 'output';
const API_HOST = 'http://localhost:3000';

function parseArgs() {
  const args = process.argv.slice(2);
  let backend = null, frontend = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--backend') backend = args[++i];
    if (args[i] === '--frontend') frontend = args[++i];
  }
  
  // Default to looking in parent directory if no paths provided
  if (!backend) backend = path.resolve(__dirname, '../../nest_docente');
  if (!frontend) frontend = path.resolve(__dirname, '../../Gestion_Docentes_New-main');
  
  return { backend, frontend };
}

function findControllerFiles(backendPath) {
  return glob.sync(path.join(backendPath, 'src/modules/**/!(*.spec).ts'))
    .filter(f => fs.readFileSync(f, 'utf8').includes('@Controller'));
}

function extractControllerInfo(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const controllerMatch = content.match(/@Controller\(([^)]*)\)/);
  if (!controllerMatch) return null;
  let controllerBase = controllerMatch[1].replace(/['"`]/g, '').trim();
  if (controllerBase.startsWith('[')) controllerBase = '';
  const module = filePath.split(path.sep).find((p, i, arr) => arr[i-1] === 'modules');
  const dtoImports = [];
  const importRegex = /import\s+\{([^}]+)\}\s+from\s+['"](.*dto.*)['"]/g;
  let m;
  while ((m = importRegex.exec(content))) {
    m[1].split(',').map(s => s.trim()).forEach(name => dtoImports.push({ name, from: m[2] }));
  }
  // Find all methods with HTTP decorators
  const methodRegex = /(@(Get|Post|Put|Delete|Patch)\(([^)]*)\))([\s\S]*?)(async\s+)?([\w$]+)\s*\(([^)]*)\)\s*{/g;
  const methods = [];
  while ((m = methodRegex.exec(content))) {
    const decorator = m[1];
    const httpMethod = m[2].toUpperCase();
    let routePath = m[3].replace(/['"`]/g, '').trim();
    if (!routePath) routePath = '';
    const methodName = m[6];
    const params = m[7];
    // Find DTOs in @Body() params
    const bodyParamMatch = params.match(/@Body\(([^)]*)\)\s*:\s*([\w$]+)/);
    let dtoFilesReferenced = [];
    if (bodyParamMatch) {
      const dtoName = bodyParamMatch[2];
      const found = dtoImports.find(d => d.name === dtoName);
      if (found) dtoFilesReferenced.push(path.join(path.dirname(filePath), found.from));
    }
    // Path params
    const pathParams = [];
    (routePath.match(/:([\w_]+)/g) || []).forEach(p => pathParams.push(p.slice(1)));
    // Path param pattern (e.g. /turno/2469-2775)
    let pathParamPattern = null;
    if (/\d+-\d+/.test(routePath)) pathParamPattern = 'number-number';
    methods.push({
      module,
      controllerFile: path.relative(process.cwd(), filePath),
      controllerBase,
      method: httpMethod,
      routePath: routePath.startsWith('/') ? routePath : '/' + routePath,
      fullPath: '/' + [controllerBase, routePath].filter(Boolean).join('/').replace(/\/+/g, '/'),
      decoratorLine: decorator.trim(),
      dtoFilesReferenced,
      pathParams,
      pathParamPattern,
      methodName
    });
  }
  return methods;
}

function findAngularServiceFiles(frontendPath) {
  return glob.sync(path.join(frontendPath, 'src/app/services/**/*.ts'));
}

function extractHttpClientUsages(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const usages = [];
  // Find http.get/post/put/delete/patch
  const httpRegex = /this\.http\.(get|post|put|delete|patch)\s*\(([^;]*)\)/g;
  let m;
  while ((m = httpRegex.exec(content))) {
    const method = m[1].toUpperCase();
    const args = m[2];
    // Try to extract URL (string literal or template)
    let urlMatch = args.match(/(['"`])([^'"`]+)\1/);
    let url = urlMatch ? urlMatch[2] : args.split(',')[0].trim();
    // Try to find method name
    const before = content.slice(0, m.index);
    const methodNameMatch = before.match(/([\w$]+)\s*\(([^)]*)\)\s*{[^}]*$/m);
    const methodName = methodNameMatch ? methodNameMatch[1] : 'unknown';
    // Find line number
    const lines = content.slice(0, m.index).split('\n');
    const line = lines.length;
    // Try to find body keys
    let bodyKeys = [];
    if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
      const bodyArg = args.split(',')[1];
      if (bodyArg) {
        const keysMatch = bodyArg.match(/\{([^}]*)\}/);
        if (keysMatch) {
          bodyKeys = keysMatch[1].split(',').map(k => k.split(':')[0].trim());
        }
      }
    }
    usages.push({
      file: path.relative(process.cwd(), filePath),
      method,
      methodName,
      url,
      line,
      bodyKeys,
      snippet: m[0]
    });
  }
  return usages;
}

function findDTOFiles(dtoFiles) {
  // Remove duplicates
  return [...new Set(dtoFiles)].filter(f => fs.existsSync(f));
}

function parseDTOFile(dtoFile) {
  const content = fs.readFileSync(dtoFile, 'utf8');
  const result = {};
  // Find exported interfaces/classes
  const exportRegex = /export\s+(interface|class)\s+(\w+)\s*{([\s\S]*?)}\s*$/gm;
  let m;
  while ((m = exportRegex.exec(content))) {
    const name = m[2];
    const body = m[3];
    const fields = [];
    // Find fields: name: type;
    const fieldRegex = /(\w+)\??:\s*([^;\n]+)/g;
    let f;
    while ((f = fieldRegex.exec(body))) {
      fields.push({
        name: f[1],
        type: f[2].trim(),
        optional: body[f.index + f[1].length] === '?'
      });
    }
    result[name] = fields;
  }
  return result;
}

function slugify(str) {
  return str.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
}

function generateCurlSample(endpoint, dtoSchemas) {
  let url = API_HOST + endpoint.fullPath.replace(/:([\w_]+)/g, (m, p) => {
    if (p.endsWith('_id')) return '2474';
    return 'VALUE';
  });
  let curl = `curl -sS -H "Authorization: Bearer $TOKEN" '` + url + `'`;
  if (['POST', 'PUT', 'PATCH'].includes(endpoint.method)) {
    let body = '{}';
    if (endpoint.dtoFilesReferenced.length && dtoSchemas) {
      const dtoFile = endpoint.dtoFilesReferenced[0];
      const dtos = dtoSchemas[dtoFile] || {};
      const dtoName = Object.keys(dtos)[0];
      if (dtoName) {
        const fields = dtos[dtoName];
        if (fields && fields.length) {
          body = '{\n' + fields.map(f => `  "${f.name}": "${f.type.includes('string') ? 'string' : f.type.includes('number') ? 123 : 'VALUE'}"`).join(',\n') + '\n}';
        }
      }
    } else {
      body = '{ /* PLEASE FILL */ }';
    }
    curl += ` -X ${endpoint.method} -H "Content-Type: application/json" -d '${body}'`;
  }
  curl += ' | jq .';
  return curl;
}

function main() {
  const { backend, frontend } = parseArgs();
  if (!fs.existsSync(backend) || !fs.existsSync(frontend)) {
    console.error('Backend or frontend path not found.');
    process.exit(1);
  }
  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR);

  // --- Backend controllers ---
  const controllerFiles = findControllerFiles(backend);
  let endpoints = [];
  let allDtoFiles = [];
  controllerFiles.forEach(f => {
    const methods = extractControllerInfo(f);
    if (methods) {
      endpoints = endpoints.concat(methods);
      methods.forEach(m => allDtoFiles = allDtoFiles.concat(m.dtoFilesReferenced));
    }
  });
  allDtoFiles = findDTOFiles(allDtoFiles);

  // --- DTO schemas ---
  const dtoSchemas = {};
  allDtoFiles.forEach(f => { dtoSchemas[f] = parseDTOFile(f); });

  // --- Frontend usages ---
  const serviceFiles = findAngularServiceFiles(frontend);
  let frontendUsages = [];
  serviceFiles.forEach(f => frontendUsages = frontendUsages.concat(extractHttpClientUsages(f)));

  // --- Map frontend usages to endpoints ---
  endpoints.forEach(ep => {
    ep.frontendCallers = frontendUsages.filter(u => ep.fullPath.includes(u.url.replace(/\$\{[^}]+\}/g, '')) || u.url.includes(ep.controllerBase));
    ep.curl = generateCurlSample(ep, dtoSchemas);
  });

  // --- Output JSON ---
  const routesJsonPath = path.join(OUTPUT_DIR, 'routes.json');
  fs.writeFileSync(routesJsonPath, JSON.stringify(endpoints, null, 2));

  // --- Output Markdown ---
  const routesMdPath = path.join(OUTPUT_DIR, 'routes.md');
  let md = `# API Endpoints Manifest\n\n| Method | Path | DTO Fields | Example curl | Frontend Callers |\n|--------|------|------------|--------------|------------------|\n`;
  endpoints.forEach(ep => {
    let dtoFields = '';
    if (ep.dtoFilesReferenced.length && dtoSchemas[ep.dtoFilesReferenced[0]]) {
      const dtos = dtoSchemas[ep.dtoFilesReferenced[0]];
      const dtoName = Object.keys(dtos)[0];
      if (dtoName) {
        dtoFields = dtos[dtoName].map(f => `${f.name}: ${f.type}${f.optional ? '?' : ''}`).join('<br>');
      }
    }
    let callers = ep.frontendCallers.map(c => `${c.file}:${c.line}`).join('<br>');
    md += `| ${ep.method} | ${ep.fullPath} | ${dtoFields} | \`${ep.curl.replace(/`/g, '\`')}\` | ${callers} |\n`;
  });
  fs.writeFileSync(routesMdPath, md);

  // --- Output curl_samples.sh ---
  const curlSamplesPath = path.join(OUTPUT_DIR, 'curl_samples.sh');
  let sh = '#!/usr/bin/env bash\n\n# Usage: TOKEN="<PUT_JWT_HERE>" ./curl_samples.sh\n# Each command prints the response.\n\nTOKEN="<PUT_JWT_HERE>"\n\n';
  endpoints.forEach(ep => {
    sh += `# ${ep.method} ${ep.fullPath}\n${ep.curl}\n\n`;
  });
  fs.writeFileSync(curlSamplesPath, sh, { mode: 0o755 });

  // --- Output fetch_responses.sh ---
  const fetchResponsesPath = path.join(OUTPUT_DIR, 'fetch_responses.sh');
  let fetchSh = '#!/usr/bin/env bash\n\n# Usage: TOKEN="<PUT_JWT_HERE>" ./fetch_responses.sh [--force]\n# This script runs curl_samples.sh and saves output to output/responses/<endpoint>.json\n# Destructive requests (POST/PUT/DELETE/PATCH) require --force.\n\nTOKEN="<PUT_JWT_HERE>"\nmkdir -p output/responses\n\n';
  endpoints.forEach(ep => {
    const slug = slugify(ep.fullPath);
    if (["POST","PUT","DELETE","PATCH"].includes(ep.method)) {
      fetchSh += `if [[ "$1" == "--force" ]]; then\n  echo "# ${ep.method} ${ep.fullPath}"\n  ${ep.curl} > output/responses/${slug}.json\nfi\n`;
    } else {
      fetchSh += `echo "# ${ep.method} ${ep.fullPath}"\n${ep.curl} > output/responses/${slug}.json\n`;
    }
  });
  fs.writeFileSync(fetchResponsesPath, fetchSh, { mode: 0o755 });

  // --- Output README.md ---
  const readmePath = path.join(OUTPUT_DIR, 'README.md');
  const readme = `# API Endpoint Manifest Generator\n\nThis directory contains generated documentation and scripts for your API.\n\n## Files\n\n- routes.json: Structured JSON of all endpoints, DTOs, and frontend callers.\n- routes.md: Markdown table of endpoints, DTOs, curl samples, and frontend usage.\n- curl_samples.sh: Bash script with curl commands for each endpoint.\n- fetch_responses.sh: Bash script to run curl_samples.sh and save responses.\n\n## Usage\n\n1. Set your JWT token in the scripts:\n\n   export TOKEN=\"<PUT_JWT_HERE>\"\n\n2. Run curl samples:\n\n   ./curl_samples.sh\n\n3. Fetch and save responses (GET only by default):\n\n   ./fetch_responses.sh\n\n   To run destructive requests (POST/PUT/DELETE/PATCH):\n\n   ./fetch_responses.sh --force\n\n4. To regenerate, run:\n\n   node ../generate_routes.js\n\n`;
  fs.writeFileSync(readmePath, readme);

  // --- Print summary ---
  const nEndpoints = endpoints.length;
  const nWithFrontend = endpoints.filter(e => e.frontendCallers.length).length;
  console.log(`\n[generate_routes] Found ${nEndpoints} endpoints, ${nWithFrontend} with frontend callers.`);
  console.log(`Output files:`);
  console.log(`  - ${routesJsonPath}`);
  console.log(`  - ${routesMdPath}`);
  console.log(`  - ${curlSamplesPath}`);
  console.log(`  - ${fetchResponsesPath}`);
  console.log(`  - ${readmePath}`);
  console.log(`\nSee output/README.md for instructions.\n`);
}

if (require.main === module) main();
