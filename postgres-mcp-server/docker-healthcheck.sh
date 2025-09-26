#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Check if the HTTP server is responding
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
  echo "postgres-mcp-server is healthy"
  exit 0
fi

# Fallback: Check if any python process is running
if pgrep -f "awslabs.postgres-mcp-server" > /dev/null 2>&1; then
  echo "postgres-mcp-server process is running"
  exit 0
fi

# Unhealthy
echo "postgres-mcp-server is not responding"
exit 1
