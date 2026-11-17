from rest_framework.pagination import PageNumberPagination


# Paginación de todos los listados: el cliente elige cuántas filas ver (?page_size=25|50|100).
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
