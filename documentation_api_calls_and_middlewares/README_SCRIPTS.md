# API Exploration Scripts

## Overview

This directory contains scripts for exploring and documenting APIs in both the NestJS backend and Angular frontend of the UMA Schedule Management System.

## Scripts

### 1. `explore_endpoints.sh`

A Bash script that scans repositories to discover HTTP endpoints.

#### Usage

```bash
./explore_endpoints.sh [options]

Options:
  -b, --backend     Scan NestJS backend endpoints
  -f, --frontend    Scan Angular frontend service calls
  -o, --output      Specify output file (default: endpoints.md)
  -v, --verbose     Enable verbose output
  -h, --help        Show this help message
```

#### Features

- Detects HTTP methods (GET, POST, PUT, DELETE)
- Identifies route parameters
- Extracts TypeScript types and interfaces
- Lists service dependencies
- Documents authentication requirements

### 2. `generate_routes.js`

A Node.js script that generates a structured API documentation manifest.

#### Usage

```bash
node generate_routes.js [options]

Options:
  --src <dir>       Source directory to scan
  --out <file>      Output file path
  --format <fmt>    Output format (md, json, yaml)
  --ignore <pat>    Ignore pattern
```

#### Features

- AST-based code analysis
- Type inference
- Documentation generation
- Code sample generation
- Cross-reference links

### 3. `fastapi_integration.py`

A Python script that provides FastAPI middleware and extensions.

#### Usage

```bash
python fastapi_integration.py [options]

Options:
  --host HOST       Host to bind (default: localhost)
  --port PORT       Port to bind (default: 8000)
  --reload         Enable auto-reload
  --workers N      Number of worker processes
```

#### Features

- API middleware
- Data validation
- Response caching
- Error handling
- Statistics generation

## Output Directory Structure

```
output/
├── api/
│   ├── backend_endpoints.md
│   ├── frontend_services.md
│   └── api_manifest.json
├── schemas/
│   ├── request_types.ts
│   └── response_types.ts
└── examples/
    ├── curl_examples.md
    └── code_samples.md
```

## Development

### Adding New Scripts

1. Create script file in root directory
2. Add documentation in this README
3. Update output templates if needed
4. Test with sample data
5. Add usage examples

### Testing

```bash
# Test endpoint discovery
./explore_endpoints.sh -b -v

# Test route generation
node generate_routes.js --src ../nest_docente/src

# Test FastAPI integration
python -m pytest tests/
```

### Output Formats

1. **Markdown**

   - Human-readable documentation
   - GitHub-compatible formatting
   - Include code blocks

2. **JSON**

   - Machine-readable format
   - Use for programmatic access
   - Include metadata

3. **YAML**
   - Configuration files
   - Human-readable structure
   - Use for templates

## Contributing

1. Fork the repository
2. Create feature branch
3. Add/modify scripts
4. Update documentation
5. Submit pull request

## Best Practices

### 1. Script Development

- Include help/usage information
- Add error handling
- Use consistent naming
- Add logging/debugging

### 2. Documentation

- Keep README updated
- Document dependencies
- Include examples
- List known issues

### 3. Output

- Use consistent formats
- Include timestamps
- Validate output
- Backup existing files

## Troubleshooting

### Common Issues

1. **Permission Denied**

   ```bash
   chmod +x explore_endpoints.sh
   ```

2. **Dependencies**

   ```bash
   npm install
   pip install -r requirements.txt
   ```

3. **Path Issues**
   ```bash
   export PATH="$PATH:$(pwd)"
   ```

### Debug Mode

```bash
# Bash script
./explore_endpoints.sh -v

# Node.js script
DEBUG=1 node generate_routes.js

# Python script
PYTHONVERBOSE=1 python fastapi_integration.py
```

## Dependencies

### System Requirements

- Bash 4.0+
- Node.js 14+
- Python 3.8+
- Git 2.0+

### Node.js Packages

```json
{
  "dependencies": {
    "typescript": "^4.5.0",
    "ts-morph": "^12.0.0",
    "commander": "^8.0.0"
  }
}
```

### Python Packages

```
fastapi>=0.68.0
uvicorn>=0.15.0
httpx>=0.19.0
pydantic>=1.8.0
```

## Support

- Report issues on GitHub
- Check documentation updates
- Join development discussions

## License

MIT License - See LICENSE file for details
