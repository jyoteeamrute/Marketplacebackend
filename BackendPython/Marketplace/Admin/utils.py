from drf_yasg.utils import swagger_auto_schema

def SwaggerView(serializer):
    def decorator(view_func):
        return swagger_auto_schema(request_body=serializer, responses={200: serializer, 201: serializer})(view_func)
    return decorator
