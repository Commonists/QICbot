import sys, os
import pywikibot
import time, datetime
import re
import marshal

# Are we in debug mode? ("-debug" at the end of the command line)
debug = False
for arg in pywikibot.handle_args():
	if arg.startswith("-debug"):
		debug = True

pageName = "Commons:Quality images candidates"
# pageName = 'USer:EuseBot/test'
pageName2 = "Commons:Quality images/"
promotedDump = pageName2 + "Recently promoted"
unassessedCat = "[[Category:Unassessed QI candidates]]"

waitDays = 2
waitDaysNoDecission = 8

vDecline = "{{/Decline|"
vWithdrawn = "{{/Withdrawn|"
vNomination = "{{/Nomination|"
vPromotion = "{{/Promotion|"
vDiscuss = "{{/Discuss|"

# note the missing closing braces, they are added below!
QITag = "{{QualityImage"

nowTime = time.mktime(datetime.datetime.utcnow().timetuple())

SITE = pywikibot.Site()

timeRE = re.compile(
	"(\d\d):(\d\d), (\d\d?) (January|February|March|April|May|June|July|August|September|October|November|December) (\d\d\d\d) \((UTC|GMT)\)"
)
userRE = re.compile("\[\[[Uu]ser:([^\|\]]+)[^\]]*\]\]")
headingRE = re.compile("===([^=]+)===")
imageRE = re.compile("\[\[([^\|\]]+)")
moveRE = re.compile("\{\{QICbotMove\|([^\|\}]+)\}\}")
galleryRE = re.compile("^\s*([Ii]mage|[Ff]ile|):([^\|]+)\s*\|")
parentRE = re.compile("^(.*)/[^/]*$")

#
# Tagging helperfunction
#
# The tag is split into two parts ( startTag, endTag )
# to check if an image on the list is already tagged the code looks
# only for startTag. That allows matching for tags with additional
# template parameters for example.
# In debug mode, only shows the diff.
#


def doTagging(imageList, startTag, endTag, summary):
	global SITE, debug
	for image in imageList:
		try:
			page = pywikibot.FilePage(SITE, image)
		except ValueError:
			print("Oops " + image + " isn't a file...")
		else:
			if page.exists():
				print("Tagging " + image)

				# follow redirects to the actual image page
				if page.isRedirectPage():
					page = page.getRedirectTarget()

				try:
					text = page.get()
				except:
					continue

				# already tagged maybe?
				oldtext = text.replace(unassessedCat, "")
				if text.find(startTag) < 0:
					text += "\n" + startTag + endTag + "\n"
					if not debug:
						# try :
						#  page.put(text, comment=summary, minorEdit=False)
						# except pywikibot.exceptions.LockedPageError:
						#  print image.encode("utf-8") + " has an editprotected description page!"
						tryPut(page, text, summary)
					else:
						pywikibot.output(
							">>> \03{lightpurple}%s\03{default} <<<" % page.title()
						)
						pywikibot.showDiff(oldtext, text)
			else:
				print("Oops " + image + " doesn't exist...")


#
# Insert image into the first gallery tags on ''text''
#


def galleryInsert(imageLines, text):
	newText = ""
	notInserted = True
	images = imageLines.split("\n")

	for line in text.split("\n"):
		# avoid doubles
		if line not in images:
			newText += line + "\n"
		if line[:8] == "<gallery" and notInserted:
			newText += imageLines
			notInserted = False

	if notInserted:
		newText = "<gallery>\n%s</gallery>\n%s" % (imageLines, text)

	return newText.rstrip("\n")


#
# Return first ''imageLimit'' images (in galleries) from ''text''
#


def gallerySample(imageLimit, text):
	global galleryRE
	firstFour = ""
	got = 0
	for line in text.split("\n"):
		image = galleryRE.search(line)
		if image != None and got < 4:
			firstFour += line + "\n"
			got += 1

	return firstFour


#
# Toss out all images except the first ''imageLimit'' in ''text''
#


def galleryLimit(imageLimit, text):
	global galleryRE
	got = 0
	newText = ""
	for line in text.split("\n"):
		image = galleryRE.search(line)
		if image != None:
			if got < imageLimit:
				newText += line + "\n"
				got += 1
		else:
			newText += line + "\n"

	return newText.rstrip("\n")


#
# Cleans up the candidate page
#


def cleanCandidatePage(text):

	import re

	emptyGalleryRE = re.compile("(<gallery[^>]*>[\s]*</gallery>)")
	emptyDayRE = re.compile("==[^=]*==[\s]*(==[^=]*==)")
	lastEmptyDayRE = re.compile("==[^=]*==[\s]*(= Consensual review =)")
	tooManyLinesRE = re.compile("\n[\s]*\n")

	text = emptyGalleryRE.sub("", text)
	text = emptyDayRE.sub(r"\1", text)
	text = lastEmptyDayRE.sub(r"\1", text)
	text = tooManyLinesRE.sub("\n\n", text)
	text = text.replace("}}\nFile:", "}}\n\nFile:")
	return text


#
# Fault tolerant page.put
#


def tryPut(page, newText, comment):
	title = page.title()
	numTry = 20
	while True:
		try:
			page.put(newText, summary=comment, watch=None, minor=False)
			break
		except pywikibot.exceptions.LockedPageError:
			print("%s is editprotected!" % title)
			break
		except:
			print("write to '%s' seems to have failed" % title)
			numTry -= 1
			if numTry == 0:
				print("giving up!")
				break
				page = pywikibot.Page(SITE, title)
				if page.exists():
					text = page.get(get_redirect=True)
					if text == newText:
						print("write did succeed")
						break




stopPage = pywikibot.Page(SITE, "Commons:Quality images candidates/stopBOT")
stopPagetext = stopPage.get(get_redirect=True)
stoptext = stopPagetext

# abort if the qicbot marker is missing from the page
if stoptext.find("<!-- QICBOT_ON -->") < 0:
	print(
		"the string <!-- QICBOT_ON --> was not found on page Commons:Quality images candidates/stopBOT"
	)
	sys.exit(0)

inGallery = False
inCRSection = False
inConsensual = 0

newText = ""
numChanges = 0
currentImage = ""
currentHeading = ""
currentStatus = 0
currentArchive = ""

# The following file is saved at $HOME
bakArchiveFileName = "tmp.archive"


def marshalData():
	global bakArchiveFileName
	f = open(bakArchiveFileName, "wb")
	marshall.dump(archive, f)
	marshall.dump(archiveCR, f)
	marshall.dump(userNote, f)
	marshall.dump(galleryMove, f)
	marshall.dump(tagImages, f)
	marshall.dump(unassessed, f)
	f.close()


consensual = ""

if os.path.isfile(bakArchiveFileName):
	f = open(bakArchiveFileName, "rb")
	archive = marshall.load(f)
	archiveCR = marshall.load(f)
	userNote = marshall.load(f)
	galleryMove = marshal.load(f)
	tagImages = marshall.load(f)
	unassessed = marshal.load(f)
	f.close()
else:
	archive = ""
	archiveCR = ""
	userNote = {}
	galleryMove = {}
	tagImages = []
	unassessed = []


#
# Move Commons:Quality images/Recently promoted images
#

page = pywikibot.Page(SITE, promotedDump)

if page.exists():
	text = page.get(get_redirect=True)
	newText = ""
	for line in text.split("\n"):
		image = galleryRE.search(line)
		dest = moveRE.search(line)
		if image != None and dest != None:
			try:
				galleryMove[dest.group(1)] += moveRE.sub("", line) + "\n"
			except KeyError:
				page2 = pywikibot.Page(SITE, pageName2 + dest.group(1))
				if page2.exists():
					galleryMove[dest.group(1)] = moveRE.sub("", line) + "\n"
				else:
					newText += line + ", '''Subgallery does not exist'''\n"
		else:
			newText += line + "\n"

	if not debug:
		# page.put( newText.rstrip("\n"), comment="moving categorized images", minorEdit=False )
		tryPut(page, newText.rstrip("\n"), "Bot: Moving categorized images")
	else:
		pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
		pywikibot.showDiff(text, newText.rstrip("\n"))

for key in list(galleryMove.keys()):
	print()
	print(key)

	try:
		# Insert into subject/type gallery
		page = pywikibot.Page(SITE, pageName2 + key)
		if page.exists():
			text = page.get(get_redirect=True)
		else:
			text = ""

		newText = galleryInsert(galleryMove[key], text)

		if text == newText:
			print("Nothing to do here")
			continue

		if not debug:
			tryPut(page, newText, "Bot: Sorted into the appropriate category")
		else:
			pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
			pywikibot.showDiff(text, newText)

		# Rebuild four image preview gallery
		pagePath = pageName2 + key
		while True:
			print("trying %s/Sample" % pagePath)
			page = pywikibot.Page(SITE, pagePath + "/Sample")
			if page.exists():
				text = page.get(get_redirect=True)
			else:
				parent = parentRE.search(pagePath)
				if parent != None:
					print("Going to parent's /Sample")
					pagePath = parent.group(1)
					continue
				else:
					print("sample gallery search failed at " + pagePath)
					break

			newText = galleryLimit(4, galleryInsert(galleryMove[key], text))

			if not debug:
				# page.put( newText, comment="rebuilding preview", minorEdit=False )
				tryPut(page, newText, "Bot: Rebuilding preview")
			else:
				pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
				pywikibot.showDiff(text, newText)
			break
	except:
		continue

#
# Open QIC page and extract nominations
#
page = pywikibot.Page(SITE, pageName + "/candidate list")
text = page.get(get_redirect=True)
oldtext = text


for line in text.split("\n"):

	discardLine = False
	archiveLine = False

	if line[:8] == "<gallery" and inGallery == False:
		inGallery = True

	elif line == "</gallery>" and inGallery == True:
		inGallery = False

	elif line == "= Consensual review =" and inConsensual == 0:
		inConsensual = 1

	elif line == "New images go below this line.  -->" and inConsensual == 1:
		inConsensual = 2
		discardLine = True
		newText += line + "\n" + consensual

	elif inConsensual == 2:

		heading = headingRE.search(line)
		if heading != None:
			if inCRSection:
				if currentStatus == 0 or currentImage == "":
					newText += currentArchive
				else:
					print(
						(
							"Closing old CR status=%d %s (%s by %s)"
							% (currentStatus, currentHeading, currentImage, currentUser)
						).encode("utf-8"),
						end=" ",
					)
					# archiveCR += currentArchive.replace('{{/', '{{../', 1)
					archiveCR += currentArchive.replace("{{/", "{{../")

					if currentStatus == 1:
						tagImages.append(currentImage)

						if currentUser == "":
							currentUser = "Dschwen"
							print("Did not find a user to notify, using Dschwen!")

						# Clean parameter numbers
						currentImage = currentImage.replace("|2=", "|3=")
						currentImage = currentImage.replace("|1=", "|2=")

						try:
							userNote[currentUser] += (
								"{{QICpromoted|" + currentImage + "}}\n"
							)
						except KeyError:
							userNote[currentUser] = (
								"{{QICpromoted|" + currentImage + "}}\n"
							)

			currentHeading = heading.group(1)
			currentImage = ""
			currentUser = ""
			currentStatus = 0
			currentArchive = ""
			inCRSection = True

		user = userRE.search(line)
		if user != None and inCRSection and currentUser == "":
			currentUser = user.group(1)

		image = imageRE.search(line)
		if image != None and inCRSection and currentImage == "":
			currentImage = image.group(1)

		if (
			line.find(vDecline) == 0
			or line.find(vWithdrawn) == 0
			or line.find(vNomination) == 0
		) and currentStatus == 0:
			currentStatus = -1

		if line.find(vPromotion) == 0 and currentStatus == 0:
			currentStatus = 1

		if inCRSection:
			discardLine = True
			currentArchive += line + "\n"

	elif inGallery == True and line.find("|") > -1:
		image, verdict = line.split("|", 1)
		verdict = verdict.strip()

		# check date
		nomTime = 0
		for match in timeRE.findall(verdict):
			try:
				sigTime = time.strptime(
					"%s:%s, %s %s %s" % match[:5], "%H:%M, %d %B %Y"
				)
			except:
				nomTime = -1
				continue
			nomTime = max(nomTime, time.mktime(sigTime))

		if nomTime == 0:
			line = (
				image + "|'''Please sign with name and date (four tildes)''' " + verdict
			)

		if nomTime == -1:
			line = (
				image + "|'''Whoops, this time sure looks invalid to me!''' " + verdict
			)

		if verdict.find(vDiscuss) == 0:
			consensual += (
				"\n===" + image + "===\n[[" + image + "|200px]]\n" + verdict + "\n"
			)
			discardLine = True

		if (nowTime - nomTime) / (
			60.0 * 60.0 * 24.0
		) > waitDaysNoDecission and nomTime > 0:

			if verdict.find(vNomination) == 0:
				print(
					(nowTime - nomTime) / (60.0 * 60.0 * 24.0),
					image.encode("utf-8"),
					" NO VERDICT!",
				)
				unassessed.append(image)
				discardLine = True
				archiveLine = True

		if (nowTime - nomTime) / (60.0 * 60.0 * 24.0) > waitDays and nomTime > 0:

			if verdict.find(vDecline) == 0 or verdict.find(vWithdrawn) == 0:
				print((nowTime - nomTime) / (60.0 * 60.0 * 24.0), image.encode("utf-8"))
				discardLine = True
				archiveLine = True

			if verdict.find(vPromotion) == 0:
				comments = verdict[len(vPromotion) :]

				# Clean parameter numbers
				imageAndComments = image + "|" + comments
				imageAndComments = imageAndComments.replace("|2=", "|3=")
				imageAndComments = imageAndComments.replace("|1=", "|2=")

				if userRE.search(line) != None:
					try:
						userNote[userRE.search(line).group(1)] += (
							"{{QICpromoted|" + imageAndComments + "\n"
						)
					except KeyError:
						userNote[userRE.search(line).group(1)] = (
							"{{QICpromoted|" + imageAndComments + "\n"
						)

				tagImages.append(image)
				discardLine = True
				archiveLine = True

	if not discardLine:
		newText += line + "\n"
	else:
		numChanges += 1
		if archiveLine:
			archive += line.replace("|{{/", "|{{../") + "\n"
			# archive += line.replace('|{{/', '|{{../', 1) + "\n"

if inConsensual < 2:
	newText += consensual

# take care of the last entry on the page (a copy from above. ToDo: refactor!)
if inCRSection:
	if currentStatus == 0 or currentImage == "":
		newText += currentArchive
	else:
		print(
			(
				"Bot: Closing old CR status=%d %s (%s by %s)"
				% (currentStatus, currentHeading, currentImage, currentUser)
			).encode("utf-8")
		)
		archiveCR += currentArchive

		if currentStatus == 1:
			tagImages.append(currentImage)

			if currentUser == "":
				currentUser = "Dschwen"
				print("Did not find a user to notify, using Dschwen!")

				# Clean parameter numbers
				currentImage = currentImage.replace("|2=", "|3=")
				currentImage = currentImage.replace("|1=", "|2=")

			try:
				userNote[currentUser] += "{{QICpromoted|" + currentImage + "}}\n"
			except KeyError:
				userNote[currentUser] = "{{QICpromoted|" + currentImage + "}}\n"


# for key in userNote.keys() :
#       print "\n==Quality Image Promotion (" + key + ")==\n" + userNote[key]
# no writing, just debugging
# print newText.encode("utf-8")
# print archiveCR.encode("utf-8")

# write extracted images
# marshalData()

newText = cleanCandidatePage(newText)

if not debug:
	# page.put(newText, comment="extract processed nominations older than %d days" % waitDays, minorEdit=False)
	tryPut(
		page,
		newText,
		"Bot: Extract processed nominations older than %d days" % waitDays,
	)

else:
	pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
	pywikibot.showDiff(oldtext, newText)

if numChanges == 0:
	print("No action taken")
	sys.exit(0)


#
# Archive removed Nominations
#

if archiveCR != "":
	archiveCR = "\n" + archiveCR.replace("{{/", "{{../")

archivePage = datetime.datetime.utcnow().strftime("/Archives %B %d %Y")
page = pywikibot.Page(SITE, pageName + archivePage)

if page.exists():
	text = page.get(get_redirect=True)
	oldtext = text
	galleryIndex = text.find("<gallery>")

	if galleryIndex > -1:
		text = (
			text[: galleryIndex + 9]
			+ "\n"
			+ archive
			+ text[galleryIndex + 9 :]
			+ archiveCR
		)
	else:
		text = "<gallery>\n" + archive + "</gallery>\n" + text + archiveCR
else:
	text = "<gallery>\n" + archive + "</gallery>\n==Consensual review==\n" + archiveCR

if not debug:
	# page.put( text, comment="archive old nominations", minorEdit=False )
	tryPut(page, text, "Bot: Archive old nominations")
else:
	pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
	pywikibot.showDiff(oldtext, text)

# delete backup files
if os.path.isfile(bakArchiveFileName):
	os.unlink(bakArchiveFileName)

#
# Tag unassessed images
#

doTagging(
	unassessed, unassessedCat, "", "Bot: Tag as unassessed Quality Image Candidate"
)


if len(tagImages) == 0:
	print("No images to promote")
	sys.exit(0)

#
# Dump all promoted images onto Commons:Quality images/Recently promoted
#

page = pywikibot.Page(SITE, promotedDump)

if page.exists():
	text = page.get(get_redirect=True)
	oldtext = text
	galleryIndex = text.find("<gallery>")

	if galleryIndex > -1:
		text = (
			text[: galleryIndex + 9]
			+ "\n"
			+ "\n".join(tagImages)
			+ text[galleryIndex + 9 :]
		)
	else:
		text = "<gallery>\n" + "\n".join(tagImages) + "</gallery>\n" + text

	newText = ""
	# text = newText

else:
	text = "<gallery>\n" + "\n".join(tagImages) + "</gallery>"

if not debug:
	# page.put( text.rstrip("\n"), comment="please sort these into the appropriate categories", minorEdit=False )
	tryPut(
		page,
		text.rstrip("\n"),
		"Bot: please sort these into the appropriate categories",
	)
else:
	pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
	pywikibot.showDiff(oldtext, text.rstrip("\n"))

#
# Tag images
#

doTagging(tagImages, QITag, "}}", "Bot: Tag promoted Quality Image")


#
# User notifications
#

for key in list(userNote.keys()):
	page = pywikibot.Page(SITE, "User talk:" + key)
	print("notifying user %s..." % key.encode("utf-8"))

	try:
		if page.exists():
			text = page.get(get_redirect=True)
			oldtext = text
		else:
			text = (
				"{{Welcome|realName=|name="
				+ key
				+ "}}<br>What better way than starting off with a Quality Image promotion could there be? :-) --~~~~\n\n"
			)

		text = text + "\n==Quality Image Promotion==\n" + userNote[key] + "\n--~~~~\n"
		if not debug:
			# page.put(text, comment='Notify user of promoted Quality Image(s)', minorEdit=False)
			tryPut(page, text, "Bot: Notify user of promoted Quality Image(s)")
		else:
			pywikibot.output(">>> \03{lightpurple}%s\03{default} <<<" % page.title())
			pywikibot.showDiff(oldtext, text)
	except:
		print("Error notifying %s" % key.encode("utf-8"))

pywikibot.stopme()
