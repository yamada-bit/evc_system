import logging
import threading

from django.utils.deprecation import MiddlewareMixin

local = threading.local()

logger = logging.getLogger(__name__)

class EvcLoggingMiddlewareUser:
    """
    logに出力するカスタム項目を取得するMiddleware
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        クライアントからのリクエスト時にrequestのusernameを取得して
        threading.local()に一時保存
        """
        if request.user:
            setattr(local, 'user', request.user.username)
        else:
            setattr(local, 'user', None)

        response = self.get_response(request)

        # response時はクリアしておく
        setattr(local, 'user', None)

        return response
class SampleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 前処理
        self.process_request(request)
        # ビューの処理
        response = self.get_response(request)
        # 後処理
        self.process_response(request, response)

        return response

    def process_request(self, request):
        print("リクエスト")

    def process_response(self, request, response):
        print("レスポンス")

class EvcLoggingMiddleware(MiddlewareMixin):
    # Djangoのビューを呼び出す前に実行される処理を記述する
    def process_view(self, request, view_func, view_args, view_kwargs): # viewを呼び出す前に実行
        logger.info(request.get_full_path())
    # ビューで例外が発生した場合に実行される処理を記述する
    def process_exception(self, request, exception):
        logger.error(exception, exc_info=True)
    """ リクエスト時のハンドリング """
    # def process_request(self, request):
    # レスポンス返却時のハンドリング
    def process_response(self, request, response):
        try:
            request_info = self.__get_request_info(request)
            user_info = self.__get_user_info__(request.user)

            msg = f"{response.status_code} {request_info} \t{user_info}"
            logger.info(msg)
        except:
            pass
            # self.logger.error(traceback.format_exc())

        return response

    def __get_request_info(self, request):
        if request.method == 'GET':
            params = self.__format_params__(dict(request.GET))
        elif request.method == 'POST':
            params = self.__format_params__(dict(request.POST))
        else:
            params = ''

        return f'{request.method} {request.get_full_path()}\tparam:[{params}]'

    def __get_user_info__(self, user):
        if user is None:
            return 'user: - '

        try:
            return f'user: {user}({user.id})'
        except:
            return 'user: - '

    def __format_params__(self, params):
        param_items = filter(lambda k, v:k != 'csrfmiddlewaretoken',params.items())
        return ', '.join([f'{key}={self.__list_str__(value)}' for (key, value) in param_items])

    def __list_str__(self, params):
        if params is None:
            return ''
        elif len(params) == 1:
            return f'{params[0]}'

        return '[' + ', '.join(f'{item}' for item in params) + ']'

