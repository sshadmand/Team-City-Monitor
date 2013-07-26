#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Copyright (c) 2011, Sean Shadmand

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

  * Neither the name of the the Beautiful Soup Consortium and All
    Night Kosher Bakery nor the names of its contributors may be
    used to endorse or promote products derived from this software
    without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE, DAMMIT.
"""
#from google.appengine.ext import webapp
import webapp2
from google.appengine.ext.webapp import util
import time
import logging
import urllib2, urllib
from BeautifulSoup import BeautifulSoup
import re, os
from google.appengine.ext import db
from google.appengine.ext.webapp import template
import datetime
import settings
import emailer
from google.appengine.api import urlfetch
from django.utils import simplejson as json
from builder_connect import BuilderConnect

from builder_connect import BuilderConnect



class Project(db.Model):
    date = db.DateTimeProperty(auto_now_add=True)
    name = db.StringProperty()
    build_id = db.IntegerProperty()
    build_type = db.StringProperty()
    build_number = db.IntegerProperty()
    build_status = db.StringProperty()
    coverage = db.FloatProperty(default=0.0)
    coverage_url = db.StringProperty(default="#")
    avg_coverage_change = db.FloatProperty(default=0.0)
    coverage_color = db.StringProperty(default="green")
    change_is = db.StringProperty(default="")
    coverage_change_indicator = ""
    coverage_color_state = ""
    ned_url = db.StringProperty(default="")
    latest = db.BooleanProperty(default=False)
    def to_dict(self):
        return dict([(p, unicode(getattr(self, p))) for p in self.properties()])

class TrackedBuild(db.Model):
    build_id = db.StringProperty()
    track_type = db.IntegerProperty()
    order_id = db.IntegerProperty()
    paused = db.BooleanProperty(default=False)
    builder = db.StringProperty(default="teamcity")
    def __str__(self):
        return self.build_id
    def to_dict(self):
        return dict([(p, unicode(getattr(self, p))) for p in self.properties()])



def get_url_as_soup(theurl):
    try:
        username = settings.TC_USERNAME
        password = settings.TC_PW

        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, theurl, username, password)
        authhandler = urllib2.HTTPBasicAuthHandler(passman)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)
        content = urllib2.urlopen(theurl).read()
        # authentication is now handled automatically for us

        soup = BeautifulSoup(content)
        return soup
    except:
        return None
    
def get_projects():
    projects = []

    bc = BuilderConnect(BuilderConnect.TEAM_CITY)
    buildtypes = bc.get_build_types()

    for bt in buildtypes:
        p = Project()
        p.name = bt['name']
        p.build_type = bt['id']
        projects.append(p)
    return projects
    
def get_all_build_states():
    projects = get_projects()
    new_projects = []
    
    for project in projects:
        try:
            bc = BuilderConnect(BuilderConnect.TEAM_CITY)
            builds = bc.get_build_states(project.build_type)
            
            project.build_status = builds.build['status']
            project.build_number = int(builds.build['number'])
            project.build_id = int(builds.build['id'])
        except:
            project.build_status = "problem"
            
    return projects

def get_code_coverage(projects):
    for project in projects:
        if project.build_status != "problem":
            #Coverage reports are different for each platform.
            
            bc = BuilderConnect(BuilderConnect.TEAM_CITY)
            
            #PYTHON/Django based coverage
            if project.build_type in ["bt6", "bt28", "bt39"]: 
                project.coverage, project.coverage_url = bc.get_coverage(project.build_type, project.build_id, "python", "index.html")
            
            #ANDROID based coverage
            elif project.build_type in ["bt7", "bt4", "bt2", "bt42"]:
                project.coverage, project.coverage_url = bc.get_coverage(project.build_type, project.build_id, "android", "coverage.html")
            
            #iOS based coverage
            elif project.build_type in ["bt8", "bt5"]:
                artdir = ""
                if project.build_type == "bt5":
                    artdir = "combined/"
                project.coverage, project.coverage_url = bc.get_coverage(project.build_type, project.build_id, "ios", "%s/index.html" % artdir)

    return projects 

def get_build_ids_to_track(as_list=False):
    tb = db.Query(TrackedBuild)
    tb.order("order_id")
    tracked_builds = tb.fetch(50)
    if as_list:
        tracked_builds_list = []
        for tb in tracked_builds:
            tracked_builds_list.append(tb.build_id)
        tracked_builds = tracked_builds_list
    return tracked_builds
    
def get_latest_builds(as_list=True):
    bts = get_build_ids_to_track()

    all_builds = []
    builds_dicts = {}
    latest_builds = []
    #pull builds form data store from list of builds to track
    #and create dictionary by build type id of each build
    #to pull data needed on build easily
    for build_to_track in bts:
        p = db.Query(Project)
        p.filter('latest =', True)
        p.order('-build_number')
        p.filter('build_type =', build_to_track.build_id)
        build = p.fetch(1)
        if len(build) > 0:
            build = build[0]
            build.tracking_type = build_to_track.track_type
            build.paused = build_to_track.paused
            builds_dicts.update({build.build_type:build})
            latest_builds.append(builds_dicts[build_to_track.build_id])            
        #if the build is not yet in data store create project place holder
        else:
            project = Project(build_type=build_to_track.build_id, latest=True)
            project.tracking_type = build_to_track.track_type
            project.paused = build_to_track.paused
            latest_builds.append(project)
            builds_dicts.update({build_to_track.build_id:project})
    
                  
    if as_list:
        return latest_builds
    else:
        return builds_dicts

  
class CheckForUpdate(webapp2.RequestHandler):


    def update_projects(self, builds_dict):
        projects = get_all_build_states()
        projects = get_code_coverage(projects)
        tracked_builds = get_build_ids_to_track(as_list=True)
        
        for project in projects:
            
            #if there has been a build since the last save
            same_build = False
            if project.build_type in builds_dict:
                print "found type in dict"
                build = builds_dict[project.build_type]
                if project.build_number == build.build_number and project.build_id == build.build_id:
                    print "same build"
                    print project.build_type
                    same_build = True
            
            #only persist when there are no duplicates in db
            #and there are no problems getting build info
            #the the build was succesful
            if not same_build and project.build_status != "problem" and project.build_type in tracked_builds:
                
                print "new build to save..."
                #new build to save. 
                #remove old build from being the latest
                build.latest = False
                build.put()
                
                #calculate the change in coverage over time
                print "persisting..."
                print project.build_type
                
                p = db.Query(Project)
                p.filter('build_type =', project.build_type)
                p.filter('build_id !=', project.build_id)
                p.filter("build_status =", "SUCCESS")
                p.order("build_id")
                average = 0.0
                change_in_avg = 0.0
                count = 0.0
                history = p.fetch(7)
                for last in history:                
                    average = last.coverage + average
                    count = count + 1.0
                if count > 0:
                    project.avg_coverage_change = round(average/count, 1)
                    change_in_avg =  project.coverage - project.avg_coverage_change
                if change_in_avg < 0:
                    project.change_is = "down"
                if change_in_avg > 0:
                    project.change_is = "up"
                #visual indecators for different levels of coverage
                if project.coverage < 50:
                    project.coverage_color = "red"
                elif project.coverage < 65:
                    project.coverage_color = "orange"
                elif project.coverage < 80:
                    project.coverage_color = "yellow"
                
                project.latest = True
                project.put()
            elif project.build_status != "problem":
                emailer.send_build_error_email(project)
            
            print "...."
            
    def get(self):
        #if there has been a build since the last save
        builds_dict = get_latest_builds(as_list=False)

        has_updated = False
        for build_dict in builds_dict:

            build = builds_dict[build_dict]
            
            bc = BuilderConnect(BuilderConnect.TEAM_CITY)
            has_updated = bc.has_new_builds(build.build_type, build.build_number)
            if has_updated:
                self.update_projects(builds_dict)
                self.response.out.write("pushed new builds")
                break   

            
        
class CoverageReport(webapp2.RequestHandler):
        
    def get_siren_embed(self):
        embed = settings.EMBED_SOUND_HTML
        return embed

    #### NEEDS IMPROVEMENT ######
    # -- function removed temporarily -- 
    #Many Datastore reads peroformed here
    #and need to be reduced
    def get_coverage_graph(self):
        bts = get_build_ids_to_track()
        longest_list_length = 0
        build_dict = {}

        for bt in bts:
            #create graph
            p = db.Query(Project)
            #p.filter("date >", datetime.datetime.now() - datetime.timedelta(days=30))
            p.filter("build_status =", "SUCCESS")
            p.filter("build_type =", bt.build_id)
            p.order("-date")
            build_stats = p.fetch(10)
            #group and associate builds and coverage qty
            for build in build_stats:
                if not (build.name in build_dict):
                    build_dict[build.name] = [str(build.name)]
                build_dict[build.name].append(build.coverage)
        
        #now add the coverage to the list for that build
        coverage_graph = []
        for key, data_points in build_dict.items():
            list_length =  len(data_points)
            if list_length > longest_list_length:
                longest_list_length = list_length
            coverage_graph.append(data_points)
        
        #numbered list representing the range the coverage is over
        coverage_range = range(1, longest_list_length)
        
        return coverage_graph, coverage_range   
            
    def get(self):
        projects = get_latest_builds()
 
         
        for project in projects:
            if project.tracking_type == 0:
                project.show_coverage = True
            append_siren = ""
            #create alerts (visual and audio) if there is a failure
            if project.build_status != "SUCCESS":
                project.coverage_color_state = "error"
                project.coverage_color = "#FF9999"
                append_siren = self.get_siren_embed();
            
            bc = BuilderConnect(BuilderConnect.TEAM_CITY)
            project.ned_url = bc.get_project_url(project.build_type)
            #project.coverage_url = "#end"


        #coverage_graph, graph_range = self.get_coverage_graph()
        
        
        
        projects.extend(get_jenkins_modules())
        
        projects.extend(get_getsat_modules())
        #projects.extend(get_deamon_modules())
        projects.extend(get_ads_server_modules())

        template_values = {
                     'projects': projects,
                     #'append_siren': append_siren,
                     #'coverage_graph': coverage_graph,
                     #'graph_range': graph_range,
                     'google_api_key': settings.GOOGLE_API_KEY,
                     'last_loaded': datetime.datetime.now().strftime("%b %d %I:%M %p ")
                 }
        path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
        self.response.out.write(template.render(path, template_values))

class Reloader(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        path = os.path.join(os.path.dirname(__file__), 'reloader.html')
        self.response.out.write(template.render(path, template_values))
        
class MainHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


def get_date_from_string(date_str):
    dt = None
    if "-" in date_str:
        import time
        if ":" in date_str:
            struct = time.strptime(date_str, "%Y-%m-%d %H:%M")
        else:
            struct = time.strptime(date_str, "%Y-%m-%d")
        from time import mktime
        dt = datetime.datetime.fromtimestamp(mktime(struct))
    return dt
    
class QueryData(webapp2.RequestHandler):
    def get(self):
        import json
        import simplejson
        import time
        #GET FILTERS
        start_date = self.request.get("start_date")
        end_date = self.request.get("end_date")
        start_date = get_date_from_string(start_date)
        end_date = get_date_from_string(end_date)
        
        #QUERY DATA
        query = db.Query(Project)

        if start_date:
            query = query.filter("date >", start_date)
        if end_date:
            query = query.filter("date <", end_date)
        
        entities = query
        final_json = {"meta":{"total_count":query.count()},"objects":[]}
        for entity in entities:
            final_json["objects"].append(entity)
        self.response.out.write( json.encode(final_json) )




class InitializeSystem(webapp2.RequestHandler):
    def get(self):
        build_ids_full = settings.TRACKED_BUILD_IDS_FULL
        build_ids_status_only = settings.TRACK_STATUS_ONLY_BUILD_IDS
        response = ""
        
        for (counter, build) in enumerate(build_ids_full):
            tb = TrackedBuild()
            tb.build_id = build
            tb.track_type = 0
            tb.order_id = counter * 10
            tb.put()
            response = response + "<p>Added %s type:Full Coverage</p>" % build

        for (counter, build) in enumerate(build_ids_status_only):
            tb = TrackedBuild()
            tb.build_id = build
            tb.track_type = 1
            tb.order_id = (counter + 10) * 10
            tb.put()
            response = response + "<p>Added %s type:Status Only</p>" % build
            
        self.response.out.write(response + "<p>....done</done>")
            
        

class BulkDelete(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        continue_deleting = True
        try:
            while continue_deleting:
                q = db.GqlQuery("SELECT __key__ FROM Project")

                if q.count() == 0:
                    continue_deleting = False
                else:
                    db.delete(q.fetch(200))
                    logging.info("Deleted 200 entries")
                    time.sleep(0.5)
        except Exception, e:
            self.response.out.write(repr(e)+'\n')
            pass
        self.response.out.write("done")
    
class GetSatList(webapp2.RequestHandler):
    def get(self):
        topics = []
        data = get_getsat_modules(return_raw_json=True)
        template_vals = {"data": data}
        path = os.path.join(os.path.dirname(__file__), 'getsat.html')
        self.response.out.write(template.render(path, template_vals))

def get_deamon_modules():
    modules = []
    try:
        url = "http://ops.getsocialize.com:8100/manage/daemon/"
        result = urlfetch.fetch(url)
        deamons = json.loads(result.content)
        for deamon in deamons:
            status = "RUNNING"
            process_id = deamon["process_id"]
            server = deamon["server_environment"]
            title = deamon["title"]
            name = "Deamon: %s - %s" % (title, server.upper())
            project = Project(name=name, coverage_url="http://ops.getsocialize.com:8100/manage/")
            if process_id < 0:       
                status = "STOPPED"
                project.coverage_color_state = "warning"
            project.build_status = status
            project.ned_url="http://ops.getsocialize.com:8100/manage/"
        
            modules.append(project)
    except:
        project = Project(name="Ops Deamon Manager", coverage_url="http://ops.getsocialize.com:8100/manage/")
        project.coverage_color_state = "error"
        project.build_status = "NOT RESPONDING"
        project.ned_url="http://ops.getsocialize.com:8100/manage/"
        modules.append(project)
        
    return modules

def get_ads_server_modules():
    modules = []
    server = "prod"
    title = "Socialize Ads"  
    cache_panel = "http://ads.getsocialize.com/adserver/cache_panel"          
    name = "Bidder: %s - %s" % (title, server.upper())
    project = Project(name=name, coverage_url=cache_panel, ned_url=cache_panel)

    result = None
    try:
        url = "http://ads.getsocialize.com/adserver/turn_bidder_on?buster=%s" % time.mktime(time.gmtime())
        result = urlfetch.fetch(url)
        logging.info("RESULTS:%s" % result.content)
    except:
        project.coverage_color_state = "error"
        project.build_status = "FETCH FAILED"
        
    if result:    
        try:        
            bidder = json.loads(result.content)
            status = "RUNNING"
            is_bidder_on = bidder["is_bidder_on"]
            if is_bidder_on <= 0:       
                status = "STOPPED"
                project.coverage_color_state = "warning"
            project.build_status = status
        except Exception, ex:
            project.coverage_color_state = "error"
            project.build_status = "NOT RESPONDING <div style='display:none;'>%s, %s</div>" % (ex, result)

    modules.append(project)

    return modules
    
    
def get_jenkins_modules():
    project_modules = []
    project_names = settings.TRACKED_JENKINS_BUILD_NAMES
    for project_name in project_names:
        build_info = get_jenkins_build_info(project_name)
        deploy_info = get_jenkins_deploy_info(project_name, build_info["build_no"])
        data = {
                "display_name": build_info["display_name"],
                "project_name": project_name,
                "build_status": build_info["status"],
                "deploy_status": deploy_info["status"],
                "color": "green",
                }
        project_modules.append( create_jenkins_project(data) )
    return project_modules

def get_jenkins_build_info(project_name):
    project_data_url = "http://jenkins.sharethis.com:8080/job/%s/api/json" % project_name
    project_data = urllib2.urlopen(project_data_url).read()
    project_json = json.loads(project_data)
    health_report = project_json["healthReport"][0]
    latest_build = project_json["builds"][0]
    project_display_name = project_json["displayName"]
    #print health_report
    #print latest_build

    latest_build_no = latest_build["number"]

    #print latest_build_no

    build_data_url = "http://23.21.170.88:8080/job/socialize-website-production/%s/api/json" % (latest_build_no)
    build_data = urllib2.urlopen(build_data_url).read()

    build_data_json = json.loads(build_data)
    #print build_data_json["result"]
    
    build_info = {
                "status": build_data_json["result"],
                "display_name": project_display_name,
                "build_no": build_data_json["number"],
                }
    return build_info
    
def get_jenkins_deploy_info(project_name, build_no):    
    console_log_url = "http://jenkins.sharethis.com:8080/job/%s/%s/consoleText" % (project_name, build_no)
    console_log = urllib2.urlopen(console_log_url).read()
    m = re.search("\{.*status.*\}", console_log)
    auto_deploy_response = m.group(0)
    auto_deploy_response_json = json.loads(auto_deploy_response)

    return auto_deploy_response_json
    
    
def create_jenkins_project(data):
    base_project_url = "http://jenkins.sharethis.com:8080/job/" + data["project_name"]
    build_status = data["build_status"].upper() 
    deploy_status = data["deploy_status"].upper()
    
    if build_status != "SUCCESS":
        color = "red"
    if deploy_status != "SUCCESS":
        color = "yellow"
    
    status = """Build: %s / Deploy: %s""" % (build_status, deploy_status)

    jenkins_project = Project(name="JENKINS: " + data["display_name"], build_status=status, ned_url=base_project_url, coverage_url=base_project_url + "/changes")
    return jenkins_project
        
        
def get_getsat_modules(return_raw_json=False):
    data = None
    projects = []
    try:
        una_url = "https://api.getsatisfaction.com/companies/socialize/topics.json?sort=unanswered&style=problem,question&status=none,pending,active&limit=100"
        result = urlfetch.fetch(una_url)
        if result.status_code == 200:
          unanswered_data = clean_getsat_data(json.loads(result.content))
          unanswered_data["type"] = "Unanswered"   
          if return_raw_json:
              projects.append(unanswered_data)
          else:
              projects.append(create_getsat_module(unanswered_data, "New"))
        open_url = "https://api.getsatisfaction.com/companies/socialize/topics.json?style=problem,question&status=none,pending,active&limit=49"
        result = urlfetch.fetch(open_url)
        if result.status_code == 200:
          open_data = clean_getsat_data(json.loads(result.content))
          open_data["type"] = "Open/Active"
          if return_raw_json:
              projects.append(open_data)
          else:
              projects.append(create_getsat_module(open_data, "Open", warning_time_limit_hours=100, problem_time_limit_hours=200))
    except:
        project = Project(name="Get Satisfaction API", coverage_url="https://api.getsatisfaction.com/companies/socialize/topics.json")
        project.coverage_color_state = "warning"
        project.build_status = "NOT RESPONDING"
        project.ned_url="https://api.getsatisfaction.com/companies/socialize/topics.json"
        projects.append(project)

        
    return projects

def clean_getsat_data(data):
    for topic in data["data"]:
        date_obj = topic["last_active_at"]
        date_obj = time.mktime(time.strptime(date_obj, "%Y/%m/%d %H:%M:%S +0000"))
        date_obj = datetime.datetime.fromtimestamp(date_obj)
        topic["last_active_at"] = date_obj
    data["data"] = sorted(data["data"], key=lambda x: x["last_active_at"] )
    return data

def create_getsat_module(data, type_name, warning_time_limit_hours=24, problem_time_limit_hours=48):
    status = "NO TOPICS"
    now = datetime.datetime.fromtimestamp(time.mktime(time.gmtime()))    
    if data and len(data["data"]) > 0:
      last_active = now - data["data"][0]["last_active_at"]
      last_active_hours = last_active.seconds/60/60
      last_active_total_hours = last_active_hours + (last_active.days*24)
      last_active_days = last_active.days
      color = "green"
      if last_active_total_hours > warning_time_limit_hours:
          color = "yellow"
      if last_active_total_hours > problem_time_limit_hours:
          color = "red"
      last_active_human = "%sD:%sH" % (str(last_active_days), str(last_active_hours) )
      if last_active_total_hours < 48:
          last_active_human = "%sH" % (str(last_active_total_hours) )          
      status = '<span style="color:%s;vertical-align: middle;">%s %s TOPICS<span style="font-size:12px;vertical-align:middle;padding-left:5px;">(%s)</span></span>' % (color, data["total"], type_name.upper(), last_active_human)
    gs_proj = Project(name="GetSatisfaction Support (%s Topics)" % type_name, build_status=status, coverage_url="/getsat_list")
    gs_proj.ned_url="/getsat_list"
    return gs_proj



def send_getsat_post(content, topic_id=2700076):
    username = ""
    password = ""

    credentials = "%s:%s" % (username, password)
    credentials = base64.b64encode( credentials.encode() )
    credentials = credentials.decode("ascii")
    headers = {'Authorization': "Basic " + credentials, "Content-type": "application/json"}

    data = """{"reply": { "content" :"%s"}}""" % content

    conn = httplib.HTTPConnection("api.getsatisfaction.com")
    conn.request("POST", "/topics/%s/replies" % topic_id, data, headers)
    response = conn.getresponse()

    data = response.read()
    conn.close()
    return data


class TrackedBuilds(webapp2.RequestHandler):
    def get(self):
        tbs = db.Query(TrackedBuild)
#        query = query.filter("date <", end_date)
        final_json = {"meta":{"total_count":tbs.count()},"coverage":[], "status":[]}
        for tb in tbs:
            if tb.track_type == 0:
                final_json["status"].append(tb.build_id)
            else:
                final_json["coverage"].append(tb.build_id)
        self.response.out.write( json.dumps(final_json) )

app = webapp2.WSGIApplication([
                                        #('/', MainHandler),
                                        ('/', MainHandler),
                                        ('/coverage_report', CoverageReport),
                                        ('/reloader', Reloader),
                                        ('/api/check_for_update', CheckForUpdate),
                                        ('/query_data', QueryData),
                                        ('/init', InitializeSystem),                                        
                                        ('/getsat_list', GetSatList),
                                        ('/bulk_delete', BulkDelete),
                                        ('/get_tracked_builds', TrackedBuilds)
                                        
                                        ],
                                         debug=True)
#old code
#    util.run_wsgi_app(application)
#if __name__ == '__main__':
#    main()
