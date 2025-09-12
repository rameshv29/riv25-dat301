# DAT301 - AI-Powered PostgreSQL Workshop Enhancements

This repository contains enhancements and additional components for the DAT301 AI-Powered PostgreSQL workshop, including MCP server implementations and workshop utilities.

## 🏗️ Architecture Overview

The workshop combines:
- **Amazon Bedrock AgentCore** for AI-powered database analysis
- **Aurora PostgreSQL** with pgvector extension
- **CloudWatch MCP Server** for monitoring integration
- **VS Code Server** for interactive development

## 📁 Repository Structure

```
riv25-dat301/
├── docker/mcp-servers/          # MCP server implementations
├── assets/                      # Workshop enhancements and utilities
├── scripts/                     # Deployment and utility scripts
└── docs/                        # Documentation and guides
```

## 🚀 Quick Start

This repository is automatically integrated with the main CloudFormation template. The workshop infrastructure will:

1. Deploy core AgentCore workshop environment
2. Clone this repository for enhancements
3. Build and deploy CloudWatch MCP server
4. Setup additional workshop utilities

## 📖 Documentation

- [Architecture Guide](docs/architecture.md)
- [MCP Integration Guide](docs/mcp-integration-guide.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## 🔧 Manual Setup

If you need to manually deploy components:

```bash
# Build CloudWatch MCP server
./scripts/mcp-deployment/build-cloudwatch-mcp.sh

# Validate setup
./scripts/workshop-utilities/validate-setup.sh
```

## 📝 License

This project is licensed under the MIT License.