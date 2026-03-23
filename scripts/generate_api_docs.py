#!/usr/bin/env python3
"""Generate API documentation from FastAPI OpenAPI schema."""

import json
from pathlib import Path

def main():
    try:
        from main import app
    except ImportError:
        print("Error: Could not import app from main.py")
        print("Make sure you're running from the project root and dependencies are installed")
        return 1
    
    # Get OpenAPI schema
    openapi_schema = app.openapi()
    
    # Create docs directory
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Save OpenAPI JSON
    openapi_path = docs_dir / "openapi.json"
    with open(openapi_path, 'w', encoding='utf-8') as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"✓ OpenAPI schema exported: {openapi_path}")
    print(f"  Endpoints: {len(openapi_schema.get('paths', {}))}")
    print(f"  Schemas: {len(openapi_schema.get('components', {}).get('schemas', {}))}")
    
    # Create markdown API reference
    md_content = generate_markdown_docs(openapi_schema)
    md_path = docs_dir / "api-reference.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"✓ API reference created: {md_path}")
    print()
    print("Next steps:")
    print("  - Review docs/api-reference.md")
    print("  - View interactive docs at: http://localhost:8000/docs")
    print("  - View OpenAPI schema at: docs/openapi.json")
    
    return 0


def generate_markdown_docs(schema: dict) -> str:
    """Generate markdown documentation from OpenAPI schema."""
    
    md = f"""# MCP SOC API Reference

**Version:** {schema.get('info', {}).get('version', '0.1.0')}  
**Base URL:** `http://localhost:8000`

---

## Overview

{schema.get('info', {}).get('description', 'MCP SOC FastAPI Broker - Multi-tenant Security Operations Center API')}

---

## Authentication

All API endpoints (except `/api/health`) require authentication via API key.

**Header:**
```
Authorization: Bearer YOUR_API_KEY
```

**Obtaining an API Key:**
1. Create a tenant: `POST /api/tenants/create`
2. Use the returned `api_key` in subsequent requests

---

## Endpoints

"""
    
    # Group endpoints by tag
    paths = schema.get('paths', {})
    tags = {}
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ['get', 'post', 'put', 'patch', 'delete']:
                tag = details.get('tags', ['default'])[0]
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append((method.upper(), path, details))
    
    # Generate documentation for each tag
    for tag, endpoints in sorted(tags.items()):
        md += f"### {tag.title()}\n\n"
        
        for method, path, details in endpoints:
            summary = details.get('summary', 'No description')
            description = details.get('description', '')
            
            md += f"#### `{method} {path}`\n\n"
            md += f"{summary}\n\n"
            
            if description:
                md += f"{description}\n\n"
            
            # Request body
            if 'requestBody' in details:
                md += "**Request Body:**\n```json\n"
                request_schema = details['requestBody'].get('content', {}).get('application/json', {}).get('schema', {})
                if '$ref' in request_schema:
                    schema_name = request_schema['$ref'].split('/')[-1]
                    md += f"// See schema: {schema_name}\n"
                md += "```\n\n"
            
            # Parameters
            params = details.get('parameters', [])
            if params:
                md += "**Parameters:**\n\n"
                md += "| Name | In | Type | Required | Description |\n"
                md += "|------|-------|------|----------|-------------|\n"
                for param in params:
                    name = param.get('name', '')
                    location = param.get('in', '')
                    param_type = param.get('schema', {}).get('type', 'string')
                    required = '✓' if param.get('required', False) else ''
                    desc = param.get('description', '')
                    md += f"| {name} | {location} | {param_type} | {required} | {desc} |\n"
                md += "\n"
            
            # Responses
            responses = details.get('responses', {})
            if responses:
                md += "**Responses:**\n\n"
                for status_code, response in responses.items():
                    desc = response.get('description', '')
                    md += f"- **{status_code}**: {desc}\n"
                md += "\n"
            
            md += "---\n\n"
    
    # Add schemas section
    md += "## Data Models\n\n"
    
    schemas = schema.get('components', {}).get('schemas', {})
    for schema_name, schema_def in sorted(schemas.items()):
        md += f"### {schema_name}\n\n"
        
        if 'description' in schema_def:
            md += f"{schema_def['description']}\n\n"
        
        properties = schema_def.get('properties', {})
        if properties:
            md += "| Field | Type | Required | Description |\n"
            md += "|-------|------|----------|-------------|\n"
            required_fields = schema_def.get('required', [])
            
            for prop_name, prop_def in properties.items():
                prop_type = prop_def.get('type', 'unknown')
                if '$ref' in prop_def:
                    prop_type = prop_def['$ref'].split('/')[-1]
                required = '✓' if prop_name in required_fields else ''
                desc = prop_def.get('description', '')
                md += f"| {prop_name} | {prop_type} | {required} | {desc} |\n"
            md += "\n"
        
        md += "---\n\n"
    
    return md


if __name__ == "__main__":
    exit(main())
