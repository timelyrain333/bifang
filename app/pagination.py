"""
自定义分页类
"""
from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """自定义分页类，支持动态page_size"""
    page_size = 20  # 默认每页数量
    page_size_query_param = 'page_size'  # 支持通过page_size参数动态设置每页数量
    max_page_size = 10000  # 最大每页数量限制，防止过大的请求导致性能问题









