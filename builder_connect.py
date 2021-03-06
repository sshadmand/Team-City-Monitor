import settings
import urllib2
from BeautifulSoup import BeautifulSoup
from google.appengine.api import urlfetch
import base64
import logging
import re

class BuilderConnect(object):
    TEAM_CITY = "teamcity"
    JENKINS = "jenkins"

    def __init__(self, system):
        self.username = settings.TC_USERNAME
        self.password = settings.TC_PW
        self.system = system

    
    def get_build_types(self):
        if self.system == self.TEAM_CITY:
            return self.__get_data("%s/httpAuth/app/rest/buildTypes" % settings.BASE_TC_URL).buildtypes

    def get_build_states(self, build_type):
        if self.system == self.TEAM_CITY:
            return self.__get_data('%s/httpAuth/app/rest/buildTypes/id:%s/builds/' % (settings.BASE_TC_URL, build_type)).builds
        
                            
    
    def has_new_builds(self, build_type, build_number):
        if build_type and build_number:
            if self.system == self.TEAM_CITY:
                logging.info("Checking for new builds....")
                url = "%s/httpAuth/app/rest/builds/?locator=buildType:%s" % (settings.BASE_TC_URL, build_type)
            
                builds_xml = self.__get_data(url)
                logging.info("HAS NEW BUILDS?")

                #if build number is of in DB cant use TC's "since" command. 
                #fixed by getting all builds and taking newest
                #TODO: check since build param and if failure use latest code check below.
                builds = []
                for build_xml in builds_xml.find("builds"):
                    builds.append(int(build_xml["number"]))
                builds = sorted(builds, reverse=True)
                
                if len(builds) == 0:
                    logging.info("YES, HAS NEW BUILDS. No Builds" )
                    return True

                if builds[0] > int(build_number):
                    logging.info("YES, HAS NEW BUILDS. Latest build is greater than current.")
                    return True

                logging.info("NO, DOES NOT HAVE NEW BUILDS.")
                return False
        else:
            return True
    
    def get_project_url(self, build_type):
        if self.system == self.TEAM_CITY:
            url = """%s/viewType.html?buildTypeId=%s&tab=buildTypeStatusDiv""" % (settings.BASE_TC_URL, build_type)
            return url
    
    def get_coverage(self, build_type, build_id, platform, path):
        if self.system == self.TEAM_CITY:
            url = "%s/httpAuth/repository/download/%s/%s:id/%s" % (settings.BASE_TC_URL, build_type, build_id, path)
            print "Checking %s" % url
            coverage_report = self.__get_data(url)
            coverage = None
            
            if coverage_report:
                logging.info("Coverage report for %s" % platform)
                if platform == "python":
                    coverage = float(coverage_report.find("span", { "class" : "pc_cov" }).contents[0].replace("%", ""))
                elif platform == "android":
                    
                    columns = coverage_report.findAll("td")
                    if len(columns) >= 5:
                        the_column = columns[5]
                        column_content = the_column.contents[0]
                        content_enc = column_content.encode('ascii','ignore')
                        coverage_str = content_enc.split("(")[0].strip().replace("%", "")
                        coverage = float(coverage_str)
                    else:
                        coverage = None

                elif platform == "ios":
                    coverage = float(coverage_report.findAll(attrs={'class' : re.compile("headerCovTableEntry")})[2].contents[0].strip().replace(" ", "").replace("%", ""))
                    print "ios coverage for %s platform is %s" % (platform, coverage)
            
            return coverage, url
                
        
    def __get_data(self, theurl):
        try:
            # passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            # passman.add_password(None, theurl, self.username, self.password)
            # authhandler = urllib2.HTTPBasicAuthHandler(passman)
            # opener = urllib2.build_opener(authhandler)
            # urllib2.install_opener(opener)
            # content = urllib2.urlopen(theurl).read()
            logging.info("Getting data from: %s " % theurl)
            result = urlfetch.fetch(theurl,
                        headers={"Authorization": 
                                 "Basic %s" % base64.b64encode("%s:%s" % (self.username, self.password) )})
            logging.info("URL Returned: %s" % result.status_code)
            content = result.content


            soup = BeautifulSoup(content)

            return soup
        except Exception, ex:
            print ex
            return None