from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        # Normalize to API Spec error shape
        data = response.data
        if isinstance(data, dict) and "detail" in data:
            response.data = {
                "error": {
                    "code": "ERROR",
                    "message": str(data["detail"]),
                }
            }
        elif isinstance(data, dict):
            response.data = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation failed",
                    "fields": data,
                }
            }
    return response
