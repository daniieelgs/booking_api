import os
import shutil
import traceback

from dotenv import load_dotenv
from access import Access
from default_config import DefaultConfig
from globals import ADMIN_IDENTITY, ADMIN_ROLE, API_PREFIX_PERFORMANCE, BOOKING_TIMEOUT_PERFORMANCE, CANCELLED_STATUS, CONFIRMED_STATUS, DATABASE_HOST, DATABASE_NAME, DATABASE_NAME_PERFORMANCE, DATABASE_PASS, DATABASE_PASS_ROOT, DATABASE_PORT, DATABASE_USER, DATABASE_USER_ROOT, DONE_STATUS, EXPORT_DATABASE_PERFORMANCE_FILENAME, JWT_ALGORITHM, LOCAL_ROLE, OVERWRITE_DATABASE_PERFORMANCE, PENDING_STATUS, SECRET_JWT, TEST_DATABASE_URI, TEST_PERFORMANCE_DATABASE_URI, TEST_PERFORMANCE_FOLDER, USER_ROLE, WEEK_DAYS
from helpers.Database import DatabaseConnection, create_database, database_exists, export_database, import_database, remove_database
from helpers.path import checkAndCreatePath
from models.status import StatusModel
from models.user_session import UserSessionModel
from app import db as default_db
from models.weekday import WeekdayModel

class ConfigTestPerformance(DefaultConfig):
    
    def __init__(self, database_uri = TEST_PERFORMANCE_DATABASE_URI, waiter_booking_status = BOOKING_TIMEOUT_PERFORMANCE, email_test_mode = True, redis_test_mode = False) -> None:
        super().__init__()
        self.database_uri = database_uri
        self.waiter_booking_status = waiter_booking_status
        self.email_test_mode = email_test_mode
        self.redis_test_mode = redis_test_mode
        self.api_prefix = API_PREFIX_PERFORMANCE
        self.database_uri = TEST_PERFORMANCE_DATABASE_URI
        
    def insertStatus(self, db):
        data = [
            {
                "status": PENDING_STATUS,
                "name": "Pending"
            },
            {
                "status": CONFIRMED_STATUS,
                "name": "Confirmed"
            },
            {
                "status": DONE_STATUS,
                "name": "Done"
            },
            {
                "status": CANCELLED_STATUS,
                "name": "Cancelled"
            }
        ]

        id = 1
        for d in data:
            model = StatusModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise
        
    def insertWeekdays(self, db):
        
        name_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        data = []
        
        for i in range(len(WEEK_DAYS)):
            data.append({
                "weekday": WEEK_DAYS[i],
                "name": name_weekdays[i]
            })

        id = 1
        for d in data:
            model = WeekdayModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise

    def __set_databse(self, db_name_original, db_user_original, db_connection: DatabaseConnection):
        
        db_name = db_connection.name
        db_connection.name = db_name_original
        
        file_sql = os.path.join(TEST_PERFORMANCE_FOLDER, EXPORT_DATABASE_PERFORMANCE_FILENAME)
        
        export_database(db_connection, file_sql)
        
        db_connection.name = db_name
        
        if not database_exists(db_connection): create_database(db_connection, file_sql, db_user_original)
        else: import_database(db_connection, file_sql)
            
    def config(self, *args, **kwargs):
        super().config(*args, **kwargs)
        
        db = kwargs['db'] if 'db' in kwargs else None
        
        print("Configuring database tests...")
        db = db or default_db

        self.public_folder = os.path.join(TEST_PERFORMANCE_FOLDER, 'public')

        checkAndCreatePath(TEST_PERFORMANCE_FOLDER, 'public')

        if OVERWRITE_DATABASE_PERFORMANCE:
            
            self.db_name_original = DATABASE_NAME
            
            self.db_connection = DatabaseConnection(DATABASE_NAME_PERFORMANCE, DATABASE_USER_ROOT, DATABASE_HOST, DATABASE_PORT, DATABASE_PASS_ROOT)
                        
            self.__set_databse(self.db_name_original, DATABASE_USER, self.db_connection)
            
        else:
            try:
                db.create_all()
                self.insertStatus(db)
                self.insertWeekdays(db)
            except:
                traceback.print_exc()
                db.session.rollback()
                    
        os.environ['PUBLIC_FOLDER'] = self.public_folder
    
    def drop(self):
        
        if OVERWRITE_DATABASE_PERFORMANCE:
            remove_database(self.db_connection)
                                
        if os.path.exists(self.public_folder):
            print("Removing folder", self.public_folder)
            shutil.rmtree(self.public_folder)


config_test = ConfigTestPerformance()