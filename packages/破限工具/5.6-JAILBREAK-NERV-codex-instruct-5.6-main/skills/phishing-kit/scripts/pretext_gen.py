# -*- coding: utf-8 -*-
"""Phishing pretext generator -- context-aware templates.

Author: zxwn
"""
import random, re

TEMPLATES = {
    "it_support": {
        "subject": "URGENT: Password Expiration Notification - {company}",
        "body": (
            "Dear {name},\n\n"
            "Your {company} account password will expire in {hours} hours.\n"
            "To maintain uninterrupted access, please verify your credentials:\n\n"
            "{link}\n\n"
            "This is an automated notification from {company} IT Services.\n"
            "Do not reply to this email.\n\n"
            "Best regards,\n{company} IT Support"
        ),
    },
    "ceo_fraud": {
        "subject": "Wire Transfer Request - CONFIDENTIAL",
        "body": (
            "{name},\n\n"
            "I need you to process an urgent wire transfer today.\n"
            "Amount: {amount}\n"
            "Destination: {destination}\n\n"
            "This is time-sensitive. Please confirm when done.\n"
            "I am in a meeting and cannot take calls.\n\n"
            "Sent from my mobile.\n\n"
            "{ceo_name}\nCEO, {company}"
        ),
    },
    "package_delivery": {
        "subject": "Failed Delivery Attempt - Tracking #{tracking}",
        "body": (
            "Your package could not be delivered on {date}.\n"
            "Reason: {reason}\n\n"
            "Reschedule delivery: {link}\n"
            "Tracking: #{tracking}\n\n"
            "{courier} Delivery Services"
        ),
    },
    "password_reset": {
        "subject": "Password Reset Request - {service}",
        "body": (
            "We received a request to reset your {service} password.\n"
            "If you did not make this request, please ignore this email.\n\n"
            "Reset your password: {link}\n"
            "This link expires in 30 minutes.\n\n"
            "{service} Security Team"
        ),
    },
    "job_offer": {
        "subject": "Job Opportunity at {company} - {position}",
        "body": (
            "Dear {name},\n\n"
            "We reviewed your profile and would like to discuss a {position} role at {company}.\n"
            "Salary range: {salary}\n\n"
            "Please submit your application here: {link}\n\n"
            "Best,\n{recruiter}\n{company} Talent Acquisition"
        ),
    },
}


def generate(scenario: str, **kwargs) -> dict:
    """Generate phishing email from template."""
    t = TEMPLATES.get(scenario)
    if not t:
        return {
            "error": "Unknown scenario: {}".format(scenario),
            "available": list(TEMPLATES.keys()),
        }
    try:
        subject = t["subject"].format(**kwargs)
        body = t["body"].format(**kwargs)
    except KeyError as e:
        return {
            "error": "Missing parameter: {}".format(e),
            "required": _extract_params(t),
        }
    return {"subject": subject, "body": body, "scenario": scenario}


def _extract_params(template: dict) -> list:
    text = template["subject"] + " " + template["body"]
    return list(set(re.findall(r"\{(\w+)\}", text)))


def randomize_sender(name: str) -> list:
    """Generate sender name variations for spoofing."""
    variations = [name, name.lower()]
    if " " in name:
        parts = name.split()
        variations.append("{}.{}".format(parts[0][0], parts[-1]))
        variations.append("{}.{}".format(parts[0], parts[-1][0]))
    return variations


def generate_link(domain: str, campaign: str, target: str = "") -> str:
    """Generate phishing link with tracking parameters."""
    import hashlib
    tid = hashlib.md5(target.encode()).hexdigest()[:8] if target else "generic"
    return "https://{}/{}/?id={}&c={}".format(domain, campaign, tid, campaign[:4])


if __name__ == "__main__":
    result = generate(
        "it_support",
        company="AcmeCorp", name="John", hours=4,
        link="https://acmecorp-secure.com/verify"
    )
    print("Subject: " + result["subject"])
    print("Body:\n" + result["body"])
