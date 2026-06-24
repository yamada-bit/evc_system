import logging

logger = logging.getLogger(__name__)

class KmsDatabaseRouter:
    """
        attendanceアプリのモデルを 'kmsdatabase' に振り分けるルーター
    """
    route_app_labels = {'Kms_Calendar','attendance'}
    def db_for_read(self, model, **hints):
        """ 読み取り時のデータベース選択 """
        if model._meta.app_label in self.route_app_labels:
            return 'kmsdatabase'
        return 'default'

    def db_for_write(self, model, **hints):
        """ 書き込み時のデータベース選択 """
        if model._meta.app_label in self.route_app_labels:
            return 'kmsdatabase'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # 異なるデータベース間（defaultのCustomUserとkmsdatabaseのAttendance）の
        # 擬似的なリレーションを許可するためにTrueを返す
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """ マイグレーションを適用するデータベースを指定 """
        if app_label in self.route_app_labels:
            return db == 'kmsdatabase'
        return db == 'default'
