import socket
import ssl
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


USER_AGENT = "SiteAegis/1.0"


# ============================================================
# URL UTILITIES
# ============================================================

def normalize_url(url: str) -> str:
    """Normalize and validate a target URL."""

    if not isinstance(url, str):
        raise ValueError("URL must be a string.")

    url = url.strip()

    if not url:
        raise ValueError("URL cannot be empty.")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if not parsed.hostname:
        raise ValueError("Invalid URL.")

    return url.rstrip("/")


def get_hostname(url: str) -> str:
    """Extract hostname from a normalized URL."""

    parsed = urlparse(normalize_url(url))

    if not parsed.hostname:
        raise ValueError("Invalid hostname.")

    return parsed.hostname


# ============================================================
# WEBSITE AVAILABILITY
# ============================================================

def check_site(url: str) -> dict:
    """Check website availability, status code, response time and IP."""

    url = normalize_url(url)
    parsed = urlparse(url)
    hostname = parsed.hostname

    result = {
        "url": url,
        "hostname": hostname,
        "status": "unknown",
        "status_code": None,
        "response_time_ms": None,
        "ip_address": None,
        "ssl_enabled": parsed.scheme == "https",
        "error": None,
    }

    # --------------------------------------------------------
    # DNS / IP
    # --------------------------------------------------------

    try:
        result["ip_address"] = socket.gethostbyname(hostname)

    except socket.gaierror:
        result["status"] = "unreachable"
        result["error"] = "DNS resolution failed."
        return result

    # --------------------------------------------------------
    # HTTP REQUEST
    # --------------------------------------------------------

    try:
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
            },
        )

        start_time = time.perf_counter()

        with urlopen(request, timeout=10) as response:
            elapsed = (time.perf_counter() - start_time) * 1000

            result["status_code"] = response.status
            result["response_time_ms"] = round(elapsed, 2)

            if 200 <= response.status < 400:
                result["status"] = "online"
            else:
                result["status"] = "warning"

    except HTTPError as exc:
        result["status_code"] = exc.code
        result["status"] = "warning"
        result["error"] = f"HTTP error {exc.code}: {exc.reason}"

    except URLError as exc:
        result["status"] = "unreachable"
        result["error"] = f"Connection error: {exc.reason}"

    except Exception as exc:
        result["status"] = "unreachable"
        result["error"] = str(exc)

    return result


# ============================================================
# SSL CERTIFICATE
# ============================================================

def check_ssl_certificate(hostname: str) -> dict:
    """Check whether a valid SSL certificate can be established."""

    result = {
        "hostname": hostname,
        "valid": False,
        "issuer": None,
        "subject": None,
        "error": None,
    }

    try:
        context = ssl.create_default_context()

        with socket.create_connection(
            (hostname, 443),
            timeout=10,
        ) as sock:

            with context.wrap_socket(
                sock,
                server_hostname=hostname,
            ) as secure_socket:

                certificate = secure_socket.getpeercert()

                result["valid"] = True
                result["subject"] = certificate.get("subject")
                result["issuer"] = certificate.get("issuer")

    except ssl.SSLCertVerificationError as exc:
        result["error"] = (
            f"SSL certificate verification failed: {exc}"
        )

    except (socket.timeout, TimeoutError):
        result["error"] = "SSL connection timed out."

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ============================================================
# SECURITY HEADERS
# ============================================================

def check_security_headers(url: str) -> dict:
    """Check important HTTP security headers."""

    url = normalize_url(url)

    security_headers = {
        "Strict-Transport-Security": "HSTS",
        "Content-Security-Policy": "CSP",
        "X-Content-Type-Options": "X-Content-Type-Options",
        "X-Frame-Options": "X-Frame-Options",
        "Referrer-Policy": "Referrer-Policy",
        "Permissions-Policy": "Permissions-Policy",
    }

    result = {
        "url": url,
        "headers": {},
        "missing": [],
        "score": 0,
        "total": len(security_headers),
        "error": None,
    }

    try:
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
            },
        )

        with urlopen(request, timeout=10) as response:

            for header, name in security_headers.items():

                value = response.headers.get(header)

                if value:
                    result["headers"][name] = value
                else:
                    result["missing"].append(name)

            present = len(result["headers"])

            if result["total"] > 0:
                result["score"] = round(
                    (present / result["total"]) * 100
                )

    except HTTPError as exc:
        result["error"] = (
            f"HTTP error {exc.code}: {exc.reason}"
        )

    except URLError as exc:
        result["error"] = (
            f"Connection error: {exc.reason}"
        )

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ============================================================
# FINDING BUILDER
# ============================================================

def create_finding(
    severity: str,
    category: str,
    title: str,
    description: str,
    evidence: str,
    impact: str,
    recommendation: str,
) -> dict:
    """Create a standardized SiteAegis security finding."""

    return {
        "severity": severity,
        "category": category,
        "title": title,
        "description": description,
        "evidence": evidence,
        "impact": impact,
        "recommendation": recommendation,
    }


# ============================================================
# RISK ENGINE
# ============================================================

def calculate_risk(scan_result: dict) -> dict:
    """
    Calculate SiteAegis security risk score.

    100 = best security posture.
    Lower scores indicate higher risk.
    """

    score = 100
    findings = []

    availability = scan_result.get("availability") or {}
    headers = scan_result.get("security_headers") or {}
    ssl_result = scan_result.get("ssl") or {}

    # --------------------------------------------------------
    # AVAILABILITY
    # --------------------------------------------------------

    if availability.get("status") != "online":

        score -= 20

        error = availability.get("error")

        evidence = (
            error
            if error
            else "The target did not return a successful online status."
        )

        findings.append(
            create_finding(
                severity="critical",
                category="Availability",
                title="Website unreachable",
                description=(
                    "The target website could not be reached "
                    "successfully by SiteAegis."
                ),
                evidence=evidence,
                impact=(
                    "Users may be unable to access the website, "
                    "and monitoring or security verification "
                    "may be incomplete."
                ),
                recommendation=(
                    "Verify DNS configuration, server availability, "
                    "network connectivity, firewall rules, and "
                    "web-server health."
                ),
            )
        )

    # --------------------------------------------------------
    # SSL / TLS
    # --------------------------------------------------------

    if availability.get("ssl_enabled", False):

        if not ssl_result.get("valid", False):

            score -= 30

            evidence = ssl_result.get("error")

            if not evidence:
                evidence = (
                    "SiteAegis could not establish a trusted "
                    "TLS connection."
                )

            findings.append(
                create_finding(
                    severity="high",
                    category="SSL/TLS",
                    title="Invalid or unavailable SSL certificate",
                    description=(
                        "SiteAegis could not establish a valid "
                        "SSL/TLS certificate for the target."
                    ),
                    evidence=evidence,
                    impact=(
                        "An invalid or untrusted certificate can "
                        "reduce transport security and expose "
                        "users to certificate warnings or "
                        "man-in-the-middle risks."
                    ),
                    recommendation=(
                        "Install a valid certificate issued by a "
                        "trusted certificate authority and verify "
                        "hostname coverage, expiration, and "
                        "certificate-chain configuration."
                    ),
                )
            )

    else:

        score -= 25

        findings.append(
            create_finding(
                severity="high",
                category="SSL/TLS",
                title="HTTPS is not enabled",
                description=(
                    "The target URL uses HTTP instead of HTTPS."
                ),
                evidence=(
                    f"Target scheme: "
                    f"{urlparse(availability.get('url', '')).scheme or 'unknown'}"
                ),
                impact=(
                    "HTTP traffic is not encrypted in transit and "
                    "may expose sensitive information to network "
                    "interception."
                ),
                recommendation=(
                    "Enable HTTPS with a valid TLS certificate and "
                    "redirect HTTP traffic to HTTPS."
                ),
            )
        )

    # --------------------------------------------------------
    # SECURITY HEADERS
    # --------------------------------------------------------

    missing_headers = headers.get("missing", [])

    header_rules = {
        "HSTS": {
            "severity": "medium",
            "penalty": 10,
            "description": (
                "HTTP Strict Transport Security was not detected."
            ),
            "impact": (
                "Browsers may be more susceptible to downgrade or "
                "first-connection interception scenarios."
            ),
            "recommendation": (
                "Configure Strict-Transport-Security after confirming "
                "that the website is fully accessible over HTTPS."
            ),
        },
        "CSP": {
            "severity": "medium",
            "penalty": 10,
            "description": (
                "Content Security Policy was not detected."
            ),
            "impact": (
                "The browser has fewer restrictions against certain "
                "content-injection and cross-site scripting scenarios."
            ),
            "recommendation": (
                "Define and deploy a restrictive "
                "Content-Security-Policy."
            ),
        },
        "X-Content-Type-Options": {
            "severity": "low",
            "penalty": 5,
            "description": (
                "X-Content-Type-Options was not detected."
            ),
            "impact": (
                "Browsers may perform MIME-type sniffing where it "
                "could otherwise be restricted."
            ),
            "recommendation": (
                "Set X-Content-Type-Options to 'nosniff'."
            ),
        },
        "X-Frame-Options": {
            "severity": "low",
            "penalty": 5,
            "description": (
                "X-Frame-Options was not detected."
            ),
            "impact": (
                "The application has less explicit protection "
                "against unwanted framing and clickjacking."
            ),
            "recommendation": (
                "Configure X-Frame-Options or an appropriate "
                "frame-ancestors directive in CSP."
            ),
        },
        "Referrer-Policy": {
            "severity": "low",
            "penalty": 3,
            "description": (
                "Referrer-Policy was not detected."
            ),
            "impact": (
                "Browsers may expose more referrer information "
                "than necessary."
            ),
            "recommendation": (
                "Configure a privacy-conscious Referrer-Policy."
            ),
        },
        "Permissions-Policy": {
            "severity": "low",
            "penalty": 2,
            "description": (
                "Permissions-Policy was not detected."
            ),
            "impact": (
                "Browser capabilities are not explicitly restricted."
            ),
            "recommendation": (
                "Define a Permissions-Policy that disables "
                "browser features your application does not require."
            ),
        },
    }

    for header in missing_headers:

        rule = header_rules.get(header)

        if not rule:
            continue

        score -= rule["penalty"]

        findings.append(
            create_finding(
                severity=rule["severity"],
                category="Security Headers",
                title=f"Missing {header}",
                description=rule["description"],
                evidence=(
                    f"{header} was not present in the HTTP "
                    "response inspected by SiteAegis."
                ),
                impact=rule["impact"],
                recommendation=rule["recommendation"],
            )
        )

    # --------------------------------------------------------
    # RESPONSE PERFORMANCE
    # --------------------------------------------------------

    response_time = availability.get("response_time_ms")

    if (
        isinstance(response_time, (int, float))
        and response_time > 3000
    ):

        score -= 5

        findings.append(
            create_finding(
                severity="low",
                category="Performance",
                title="Slow response time",
                description=(
                    "The target response time exceeded "
                    "the SiteAegis 3-second threshold."
                ),
                evidence=(
                    f"Measured response time: {response_time} ms."
                ),
                impact=(
                    "Slow responses can negatively affect user "
                    "experience and may indicate server, network, "
                    "or application performance issues."
                ),
                recommendation=(
                    "Investigate server processing time, database "
                    "queries, external dependencies, caching, "
                    "network latency, and resource utilization."
                ),
            )
        )

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    score = max(0, min(100, score))

    if score >= 80:
        risk_level = "low"
    elif score >= 60:
        risk_level = "medium"
    elif score >= 40:
        risk_level = "high"
    else:
        risk_level = "critical"

    # --------------------------------------------------------
    # FINDING SUMMARY
    # --------------------------------------------------------

    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for finding in findings:

        severity = finding.get("severity")

        if severity in severity_counts:
            severity_counts[severity] += 1

    return {
        "score": score,
        "risk_level": risk_level,
        "findings_count": len(findings),
        "severity_counts": severity_counts,
        "findings": findings,
    }


# ============================================================
# COMPLETE SITE SCAN
# ============================================================

def run_site_scan(url: str) -> dict:
    """Run the complete SiteAegis security scan."""

    normalized_url = normalize_url(url)
    hostname = get_hostname(normalized_url)

    site_result = check_site(normalized_url)

    headers_result = check_security_headers(normalized_url)

    ssl_result = check_ssl_certificate(hostname)

    scan_result = {
        "target": normalized_url,
        "availability": site_result,
        "security_headers": headers_result,
        "ssl": ssl_result,
    }

    scan_result["risk"] = calculate_risk(scan_result)

    return scan_result