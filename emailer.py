from google.appengine.api import mail
import settings

def send_build_error_email(project):
    pass
    # mail.send_mail(sender=settings.EMAIL_SENDER,
    #                   to="dev@getsocialize.com",
    #                   subject="Someone Broke the Build",
    #                   body="""
    #                   Someone broke the build and it could be you!
    #                   
    #                   Check out TMC (ned) to see what you can do to help.
    #                   
    #                   """)