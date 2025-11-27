# MetaTrader 5 MCP Server - Usage Guide for AI Agents

## Overview

This guide helps AI agents correctly use the MetaTrader 5 MCP Server to query market data.

---

## ✅ Correct Tool Usage

### Tool Name
`execute_mt5`

### Tool Call Structure
```json
{
  "name": "execute_mt5",
  "arguments": {
    "command": "mt5.symbol_info('BTCUSD')._asdict()"
  }