# AWS Deployment Guide

This guide covers the deployment of the DocuSense System on AWS EC2.

## EC2 Instance Sizing Recommendation

Based on the system requirements—specifically a **maximum file upload size of 10 MB**—the resource footprint for both memory and computation is minimal. 

We recommend the following instance type:

### Recommended: `t3.small` (2 vCPU, 2 GiB RAM)
- **Why this choice?** 
  - 10 MB files do not require massive amounts of RAM, even when loading them fully into memory for processing or sending them to an external OCR API.
  - A `t3.small` provides 2 GB of RAM, which gives enough overhead to comfortably run the web framework, background workers, and handle multiple concurrent uploads without crashing due to Out Of Memory (OOM) errors.
  - It is highly cost-effective and provides burstable CPU performance, perfectly matching the intermittent nature of document uploads.

### Alternative (For very low traffic): `t3.micro` (2 vCPU, 1 GiB RAM)
- If you are optimizing strictly for cost (and possibly the AWS Free Tier) and only expect a few users at a time, a `t3.micro` will suffice. However, you must ensure that your application dependencies and the OS do not exceed 1 GB of memory.

**Note:** You do **not** need expensive compute-optimized (`c7i-flex`) or memory-optimized (`m7i-flex`) instances unless you plan to run heavy machine learning models or local OCR (like Tesseract) directly on the machine at a high scale.

## Basic Deployment Steps

1. **Provision an EC2 Instance:**
   - Launch a `t3.small` instance running Ubuntu 22.04 LTS (or your preferred Linux distribution).
   - Ensure you have a Key Pair to SSH into the instance.

2. **Configure Security Groups:**
   - Allow Inbound SSH (Port 22) from your IP.
   - Allow Inbound HTTP (Port 80) and HTTPS (Port 443) from anywhere (0.0.0.0/0).

3. **Install Dependencies:**
   - SSH into your server and install Python 3.9+, pip, and Git.
   - Clone the repository and run `pip install -r requirements.txt`.

4. **Set Up Environment Variables:**
   - Create a `.env` file based on `.env.example` in the project root.
   - Configure your AWS credentials if you are integrating with AWS Textract or S3.

5. **Run the Application:**
   - Use a production-ready application server like `gunicorn` or `uvicorn` (depending on the framework).
   - Set up a reverse proxy using Nginx to route traffic from Port 80 to your application's port.

6. **Process Management:**
   - Use `systemd` or `supervisor` to ensure the application restarts automatically if the server reboots.
