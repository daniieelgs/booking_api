import os
import shutil
import traceback
from access import Access
from default_config import DefaultConfig
from globals import ADMIN_IDENTITY, ADMIN_ROLE, CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, JWT_ALGORITHM, LOCAL_ROLE, PENDING_STATUS, SECRET_JWT, TEST_DATABASE_URI, USER_ROLE, WEEK_DAYS
from models.status import StatusModel
from models.user_session import UserSessionModel
from app import db as default_db
from models.weekday import WeekdayModel

class ConfigTest(DefaultConfig):
    
    def __init__(self, database_uri = TEST_DATABASE_URI, waiter_booking_status = None, email_test_mode = True, redis_test_mode = True) -> None:
        super().__init__(email_test_mode = email_test_mode, redis_test_mode = redis_test_mode)
                
        self.database_uri = database_uri
        self.waiter_booking_status = waiter_booking_status
        self.email_test_mode = email_test_mode
        self.redis_test_mode = redis_test_mode
       
    def insertUserSession(self, db):
        
        data = [
            {
                "user": ADMIN_ROLE,
                "name": "Admin"
            },
            {
                "user": LOCAL_ROLE,
                "name": "Local"
            },
            {
                "user": USER_ROLE,
                "name": "User"
            }
        ]

        id = 1
        for d in data:
            model = UserSessionModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise
        
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

    def createAdminToken(self, db):
        access = Access(db_sqlite='instance/' + config_test.database_uri.split('///')[-1], ADMIN_IDENTITY = ADMIN_IDENTITY, ADMIN_ROLE = ADMIN_ROLE, SECRET_JWT = SECRET_JWT, JWT_ALGORITHM = JWT_ALGORITHM)
        
        db = access.connectToDB()

        self.ADMIN_TOKEN = access.makeToken(db, 1, copy_on_clipboard = False)

    def config(self, *args, **kwargs):
        super().config(*args, **kwargs)
        
        db = kwargs['db'] if 'db' in kwargs else None
        
        print("Configuring database tests...")
        db = db or default_db
        
        self.insertUserSession(db)
        self.insertStatus(db)
        self.insertWeekdays(db)
        
        self.createAdminToken(db)
        
        os.environ['PUBLIC_FOLDER'] = 'tests/public'
    
    def drop(self, locals):
        folder = os.getenv('PUBLIC_FOLDER', None)
        
        for id in locals:
            path = os.path.join(os.getcwd(), folder, id)
            if os.path.exists(path):
                print("Removing folder", path)
                shutil.rmtree(path)

        
        
def getUrl(*url) -> str:
    return f"{config_test.api_prefix}/{'/'.join([str(u) for u in url])}"

def setParams(url, **params) -> str:
    return f"{url}?{'&'.join([f'{param}={params[param]}' for param in params])}"

config_test = ConfigTest()