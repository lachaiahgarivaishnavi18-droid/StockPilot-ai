"""Create an explicit local approver account; never run automatically in production."""
import argparse
import getpass
from sqlalchemy import select
from app.database import Base,engine,SessionLocal
from app.models import User
from app.security import passwords

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--email',default='demo@stockpilot.local')
    parser.add_argument('--demo',action='store_true',help='Create synthetic data and use the documented local demo password')
    args=parser.parse_args()
    password='StockPilot-demo-2026!' if args.demo else getpass.getpass('New admin password (10+ characters): ')
    if len(password)<10: raise ValueError('Password must have at least 10 characters')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing=db.scalar(select(User).where(User.email==args.email))
        if not existing:
            db.add(User(email=args.email,name='Demo Operator' if args.demo else 'Administrator',role='admin',password_hash=passwords.hash(password)))
        if args.demo:
            from app.seed import seed
            seed(db)
        db.commit()
    print('Account ready:',args.email)
    if args.demo: print('Local demo password: StockPilot-demo-2026! (do not use in production)')

if __name__=='__main__': main()
