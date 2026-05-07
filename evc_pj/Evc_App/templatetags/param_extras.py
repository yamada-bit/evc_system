from django import template

register = template.Library()

@register.simple_tag
def url_replace(request, key, value):
    url_dict = request.GET.copy()
    url_dict[key] = value
    return url_dict.urlencode()

# def query_replace(request, **kwargs):
#     url_dict = request.GET.copy()
#     for k, v in kwargs.items():
#         url_dict[k] = v
#     return url_dict.urlencode()    
@register.simple_tag
def query_replace(request, key, value):
    url_dict = request.GET.copy()
    url_dict[key] = value
    url_dict['act'] = ''
    return url_dict.urlencode()
