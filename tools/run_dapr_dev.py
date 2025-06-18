#!/usr/bin/env python3

"""
Development helper for running Dapr sidecar with conversation components.

This script helps developers quickly start a Dapr sidecar with conversation components
for testing the Python SDK conversation streaming functionality.

Usage:
    python tools/run_dapr_dev.py [options]

Options:
    --build         Build daprd binary before running
    --port          HTTP port for sidecar (default: 3500)  
    --grpc-port     gRPC port for sidecar (default: 50001)
    --app-id        Application ID (default: test-app)
    --log-level     Log level (default: info)
    --components    Path to components directory (default: auto-created)
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DAPR_REPO = REPO_ROOT.parent / "dapr"

def check_dapr_repo():
    """Check if local dapr repository exists."""
    if not DAPR_REPO.exists():
        print(f"❌ Error: Dapr repository not found at {DAPR_REPO}")
        print("Please clone the dapr repository at ../dapr relative to python-sdk")
        sys.exit(1)
    return True

def build_daprd():
    """Build the daprd binary."""
    print("🔨 Building daprd binary...")
    try:
        result = subprocess.run(
            ["make", "build"], 
            cwd=DAPR_REPO, 
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Build successful!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def get_daprd_binary():
    """Get the path to the daprd binary."""
    # Check for platform-specific binary
    import platform
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    if arch == "x86_64":
        arch = "amd64"
    elif arch in ["arm64", "aarch64"]:
        arch = "arm64"
    
    binary_path = DAPR_REPO / "dist" / f"{system}_{arch}" / "release" / "daprd"
    
    if binary_path.exists():
        return binary_path
    
    # Fallback to root directory
    fallback_path = DAPR_REPO / "daprd"
    if fallback_path.exists():
        return fallback_path
        
    print(f"❌ Error: daprd binary not found at {binary_path} or {fallback_path}")
    print("Try running with --build to build the binary")
    sys.exit(1)

def create_conversation_components(components_dir):
    """Create conversation component configuration."""
    components_dir = Path(components_dir)
    components_dir.mkdir(exist_ok=True)
    
    echo_component = components_dir / "echo-conversation.yaml"
    echo_component.write_text("""apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: echo
spec:
  type: conversation.echo
  version: v1
  metadata:
  - name: key
    value: testkey
""")
    
    print(f"📝 Created conversation components in {components_dir}")
    return components_dir

def run_daprd(args):
    """Run the daprd sidecar."""
    binary_path = get_daprd_binary()
    
    # Create temporary components directory if not specified
    if not args.components:
        temp_dir = tempfile.mkdtemp(prefix="dapr-dev-")
        components_dir = create_conversation_components(temp_dir)
    else:
        components_dir = Path(args.components)
    
    cmd = [
        str(binary_path),
        "--app-id", args.app_id,
        "--dapr-http-port", str(args.port),
        "--dapr-grpc-port", str(args.grpc_port),
        "--log-level", args.log_level,
        "--enable-app-health-check=false",
        "--resources-path", str(components_dir)
    ]
    
    print(f"🚀 Starting Dapr sidecar...")
    print(f"   Binary: {binary_path}")
    print(f"   App ID: {args.app_id}")
    print(f"   HTTP Port: {args.port}")
    print(f"   gRPC Port: {args.grpc_port}")
    print(f"   Components: {components_dir}")
    print(f"   Command: {' '.join(cmd)}")
    print("\n📡 Sidecar output:")
    print("-" * 50)
    
    try:
        # Run the sidecar
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Stopping sidecar...")
    except subprocess.CalledProcessError as e:
        print(f"❌ Sidecar failed: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary directory
        if not args.components and temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(description="Run Dapr sidecar for development")
    parser.add_argument("--build", action="store_true", help="Build daprd binary before running")
    parser.add_argument("--port", type=int, default=3500, help="HTTP port (default: 3500)")
    parser.add_argument("--grpc-port", type=int, default=50001, help="gRPC port (default: 50001)")
    parser.add_argument("--app-id", default="test-app", help="Application ID (default: test-app)")
    parser.add_argument("--log-level", default="info", help="Log level (default: info)")
    parser.add_argument("--components", help="Path to components directory")
    
    args = parser.parse_args()
    
    print("🧪 Dapr Development Helper")
    print("=" * 40)
    
    # Check prerequisites
    check_dapr_repo()
    
    # Build if requested
    if args.build:
        if not build_daprd():
            sys.exit(1)
    
    # Run the sidecar
    run_daprd(args)

if __name__ == "__main__":
    main() 