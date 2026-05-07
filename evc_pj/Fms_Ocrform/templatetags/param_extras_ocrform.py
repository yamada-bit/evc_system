from django import template

register = template.Library()

@register.simple_tag
def url_replace(request, key, value):
    url_dict = request.GET.copy()
    url_dict[key] = value
    return url_dict.urlencode()

# listで削除処理(act:del)の対応 ページ遷移でactをクリア
@register.simple_tag
def query_replace(request, key, value):
    url_dict = request.GET.copy()
    url_dict[key] = value
    url_dict['act'] = ''
    return url_dict.urlencode()