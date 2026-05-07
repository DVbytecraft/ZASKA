from app.core.email import send_email as _send_email
from app.core.email import send_otp_email as _send_otp_email


class EmailService:
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str = "",
    ) -> bool:
        return _send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        return _send_otp_email(to_email=to_email, otp_code=otp_code)
