class KmsDatabaseRouter:
    def db_for_read(self, model, **hints):
        """ 読み取り時のデータベース選択 """
        if model._meta.app_label == 'Kms_Attendance':
            return 'kmsdatabase'
        if model._meta.app_label == 'Kms_Calendar':
            return 'kmsdatabase'
        return 'default'

    def db_for_write(self, model, **hints):
        """ 書き込み時のデータベース選択 """
        if model._meta.app_label == 'Kms_Attendance':
            return 'kmsdatabase'
        if model._meta.app_label == 'Kms_Calendar':
            return 'kmsdatabase'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """ 異なるDB間でのリレーションを許可するか """
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """ マイグレーションを適用するデータベースを指定 """
        if app_label == 'Kms_Attendance':
            return db == 'kmsdatabase'
        if app_label == 'Kms_Calendar':
            return db == 'kmsdatabase'
        return db == 'default'
