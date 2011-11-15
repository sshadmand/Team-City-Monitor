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
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
import urllib2, urllib
from BeautifulSoup import BeautifulSoup
import re, os
from google.appengine.ext import db
from google.appengine.ext.webapp import template
import datetime
import settings
import emailer

#TODO: should be called BuildLog
class Project(db.Model):
	date = db.DateTimeProperty(auto_now_add=True)
	name = db.StringProperty()
	build_id = db.IntegerProperty()
	build_type = db.StringProperty()
	build_number = db.IntegerProperty()
	build_status = db.StringProperty()
	coverage = db.FloatProperty(default=0.0)
	coverage_url = db.StringProperty()
	avg_coverage_change = db.FloatProperty(default=0.0)
	coverage_color = db.StringProperty(default="green")
	change_is = db.StringProperty(default="")
	coverage_change_indicator = ""
	coverage_color_state = ""
	ned_url = ""

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
	
def get_build_types():
	projects = []
	#get build types and names
	soup = get_url_as_soup("%s/httpAuth/app/rest/buildTypes" % settings.BASE_TC_URL)
	for bt in soup.buildtypes:
		p = Project()
		p.name = bt['name']
		p.build_type = bt['id']
		projects.append(p)
	return projects
	
def get_all_build_states():
	projects = get_build_types()
	new_projects = []
	
	for project in projects:
		try:
			theurl = '%s/httpAuth/app/rest/buildTypes/id:%s/builds/' % (settings.BASE_TC_URL, project.build_type)
			soup = get_url_as_soup(theurl)
			project.build_status = soup.builds.build['status']
			project.build_number = int(soup.builds.build['number'])
			project.build_id = int(soup.builds.build['id'])
		except:
			project.build_status = "problem"
			
	return projects

def get_code_coverage(projects):
	for project in projects:
		if project.build_status != "problem":
			#Coverage reports are different for each platform.
			
			#PYTHON/Django based coverage
			if project.build_type in ["bt6"]: 
				project.coverage_url = "%s/httpAuth/repository/download/%s/%s:id/index.html" % (settings.BASE_TC_URL, project.build_type, project.build_id)		
				soup = get_url_as_soup(project.coverage_url)
				if soup:
					project.coverage = float(soup.find("span", { "class" : "pc_cov" }).contents[0].replace("%", ""))
			
			#ANDROID based coverage
			elif project.build_type in ["bt7", "bt4", "bt2"]:
				project.coverage_url = "%s/httpAuth/repository/download/%s/%s:id/coverage.html" % (settings.BASE_TC_URL, project.build_type, project.build_id)		
				soup = get_url_as_soup(project.coverage_url)
				if soup:
					project.coverage = float(soup.findAll("td")[5].contents[0].encode('ascii','ignore').split("(")[0].strip().replace("%", ""))
			
			#iOS based coverage
			elif project.build_type in ["bt8", "bt5"]:
				project.coverage_url = "%s/httpAuth/repository/download/%s/%s:id/index.html" % (settings.BASE_TC_URL, project.build_type, project.build_id)		
				soup = get_url_as_soup(project.coverage_url)
				if soup:
					project.coverage = float(soup.findAll(attrs={'class' : re.compile("headerCovTableEntry")})[2].contents[0].strip().replace(" ", "").replace("%", ""))
	return projects	

def get_build_ids_to_track():
	return settings.TRACKED_BUILD_IDS

#### NEEDS IMPROVEMENT ######
#Many Datastore reads peroformed here
#and need to be reduced
def get_latest_builds():
	bts = get_build_ids_to_track()
	builds = []
	for bt in bts:
		p = db.Query(Project)
		p.filter('build_type =', bt)
		p.order('-build_number')
		build = p.fetch(1)
		
		if build:			
			builds.append(build[0])
		else:
			builds.append(Project(build_type=bt))
		
		    
	return builds
		
class CheckForUpdate(webapp.RequestHandler):
	def needs_build_updated(self, build_type, build_number):
		if build_type and build_number:
			url = "%s/httpAuth/app/rest/builds/?locator=buildType:%s,sinceBuild:%s" % (settings.BASE_TC_URL, build_type, build_number)
			soup = get_url_as_soup(url)
			response = False
			if soup:
				change_count = soup.find("builds")
				if int(change_count["count"]) > 0:
					response = True
			return response
		else:
			return True


    #### NEEDS IMPROVEMENT ######
    #Many Datastore reads peroformed here
    #and need to be reduced
	def update_projects(self):
		projects = get_all_build_states()
		projects = get_code_coverage(projects)
		for project in projects:

			#if there has been a build since the last save
			p = db.Query(Project)
			p.filter('build_type =', project.build_type)
			p.filter('build_number =', project.build_number)
			p.filter('build_id =', project.build_id)
			results_count = p.count()
			
			#only persist when there are no duplicates in db
			#and there are no problems getting build info
			#the the build was succesful
			if results_count == 0 and project.build_status != "problem":
				#calculate the change in coverage over time
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

				project.put()
			elif project.build_status != "problem":
			    emailer.send_build_error_email(project)
			
	def get(self):
		#if there has been a build since the last save
		builds = get_latest_builds()
		has_updated = False
		for build in builds:				
			has_updated = self.needs_build_updated(build.build_type, build.build_number)
			if has_updated:
				self.update_projects()
				self.response.out.write("pushed new builds")
				break	

			
		
class CoverageReport(webapp.RequestHandler):
		
	def get_siren_embed(self):
		embed = settings.EMBED_SOUND_HTML
		return embed

    #### NEEDS IMPROVEMENT ######
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
			p.filter("build_type =", bt)
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
			if not (project.build_type in settings.TRACK_STATUS_ONLY_BUILD_IDS):
			    project.show_coverage = True
			append_siren = ""
			#create alerts (visual and audio) if there is a failure
			if project.build_status != "SUCCESS":
				project.coverage_color_state = "style='background: red;border: 2px solid darkRed;margin: 9px;'"
				project.coverage_color = "#FF9999"
				append_siren = self.get_siren_embed();

			project.ned_url = """%s/viewType.html?buildTypeId=%s&tab=buildTypeStatusDiv""" % (settings.BASE_TC_URL, project.build_type)
			
		#coverage_graph, graph_range = self.get_coverage_graph()
		template_values = {
		             'projects': projects,
					 'append_siren': append_siren,
					 #'coverage_graph': coverage_graph,
					 #'graph_range': graph_range,
					 'google_api_key': settings.GOOGLE_API_KEY,
					 'last_loaded': datetime.datetime.now().strftime("%b %d %I:%M %p ")
		         }
		path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
		self.response.out.write(template.render(path, template_values))

class Reloader(webapp.RequestHandler):
	def get(self):
		template_values = {}
		path = os.path.join(os.path.dirname(__file__), 'reloader.html')
		self.response.out.write(template.render(path, template_values))
		
class MainHandler(webapp.RequestHandler):
	def get(self):
		template_values = {}
		path = os.path.join(os.path.dirname(__file__), 'index.html')
		self.response.out.write(template.render(path, template_values))

def main():
    application = webapp.WSGIApplication([
										#('/', MainHandler),
										('/', CoverageReport),
										('/coverage_report', CoverageReport),
										('/reloader', Reloader),
										('/api/check_for_update', CheckForUpdate),
										],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
