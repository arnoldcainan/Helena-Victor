from django.conf import settings


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.CSP_ENABLED:
            return response
        policy = self.build_policy(settings.CSP_DIRECTIVES)
        header = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        response[header] = policy
        return response

    @staticmethod
    def build_policy(directives):
        parts = []
        for name, sources in directives.items():
            value = " ".join(sources)
            parts.append(f"{name} {value}".strip())
        return "; ".join(parts)
