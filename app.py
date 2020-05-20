# TODO:
# forgot password


#import libraries
from flask import Flask, request, render_template, session, url_for, redirect
from flask_session import Session
from tempfile import mkdtemp
from base64 import b64encode
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import hashlib
from random import randint
from helpers import  login_required,match,dbexecute

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

#begin session
app.config.from_object(__name__)
Session(app)

@app.route('/', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        session.clear()

        # Ensure username was submitted
        if not request.form.get("email"):
            return ("must provide email")

        # Ensure password was submitted
        elif not request.form.get("pass"):
            return ("must provide password")

        # Query database for username
        sturows = dbexecute("SELECT * FROM student WHERE email = ?",
                             (request.form.get("email"),))

        coachrows = dbexecute("SELECT * FROM coach WHERE email = ?",
                             (request.form.get("email"),))

        teachrows = dbexecute("SELECT * FROM teacher WHERE email = ?",
                             (request.form.get("email"),))

        pw = hashlib.md5(request.form.get("pass").encode())
        # check if user is a student and has correct password
        if len(sturows) == 1 and pw.hexdigest() == sturows[0]["password"]:
            #set session email address
            session["user_id"] = request.form.get("email")
            session["acc_type"] = "student"
            return redirect(url_for("profile"))

        # check if user is a coach and has correct password
        if len(coachrows) == 1 and pw.hexdigest() == coachrows[0]["password"]:
            #set session email address
            session["user_id"] = request.form.get("email")
            session["acc_type"] = "coach"
            return redirect(url_for("coach"))

        # check if user is a teacher and has correct password
        if len(teachrows) == 1 and pw.hexdigest() == teachrows[0]["password"]:
            #set session email address
            session["user_id"] = request.form.get("email")
            session["acc_type"] = "teacher"
            return redirect(url_for("teacher"))

        return render_template("index.html",errorMessage = "Incorrect Email/Password")

    #if it is a GET request
    else:
        return render_template("testing.html")



@app.route('/profile')
@login_required
def profile():
    #must be a student to access profile
    if session["acc_type"] != "student":
        return render_template("error.html",errorMessage="You are not a student.")

    #select all tasks
    tasks = dbexecute("SELECT * FROM task")

    # get unique code
    uniqueCode = dbexecute("SELECT uniqueCode FROM student WHERE email = ?",(session["user_id"],))[0]


    #select wagon wheel data for the student
    try:
        initWagonwheel = dbexecute("SELECT * FROM wagonwheel WHERE studentEmail = ? AND initOrFinal = 0",(session["user_id"],))[0]
    except:
        return render_template("fillwheel.html",wagonNum=0)
    try:
        finalWagonwheel = dbexecute("SELECT * FROM wagonwheel WHERE studentEmail = ? AND initOrFinal = 1",(session["user_id"],))[0]
    except:
        finalWagonwheel = {}
    # try to select student's evaluation
    try:
        evaluation = dbexecute("SELECT * FROM studentEvaluation WHERE email = ?",(session["user_id"],))[0]
    #set evaluation to blank if it hasn't been entered
    except:
        evaluation=""
    # if the student has not filled the wagon wheel yet, redirect them to fill it 
    if len(initWagonwheel) == 0:
        return render_template("fillwheel.html",wagonNum=0)
    #select tasks user has completed
    usertasks = dbexecute("SELECT * FROM studentTask WHERE studentEmail = ?",(session["user_id"],))

    for task in tasks:
        #set deafults for all tasks
        task["text"]= "Enter text here"
        task["image"] = "No"
        #update image and task data if it has been completed
        for usertask in usertasks:
            if task["taskID"] == usertask["taskID"]:
                task["text"] = usertask["text"]
                #update image data if it has been uploaded
                if usertask["photo"]!= None:
                    task["image"] = b64encode(usertask["photo"]).decode("utf-8")

    

    #render profile with data
    return render_template("imageupload.html", eval=evaluation, initWheel =initWagonwheel,tasks=tasks,finalWheel = finalWagonwheel,unique = uniqueCode)


#view current pairs
@app.route('/viewpairs')
@login_required
def viewpairs():
    #sql aggregate function
    #select all pairs in the current iteration
    pairs = dbexecute("SELECT coach.firstName as coachFName,coach.lastName as coachLName,\
        student.firstName as stuFName,student.lastName as stuLName FROM coach,student,pairs \
        WHERE pairs.coachEmail = coach.email and pairs.studentEmail = student.email and \
        pairs.iteration = (SELECT MAX(iteration) FROM pairs);")
     #return template with current pair data
    return render_template("viewpairs.html",pairs=pairs)



@app.route('/teacher')
@login_required
def teacher():


    if session["acc_type"] != "teacher":
        return render_template("error.html",errorMessage="You are not a teacher.")

    #sql aggregate query
    #select all students in current iteration
    students = dbexecute("SELECT email,firstName,lastName,uniqueCode FROM student WHERE email in \
        (SELECT studentEmail FROM pairs WHERE iteration = (SELECT MAX(iteration) FROM pairs))")
    #maximum amount of tasks/wagon wheel/eval to be completed for the progress bar
    maxAmount = len(dbexecute("SELECT * FROM task")) + 3
    for student in students:
        # for every student get the number of tasks etc. completed
        wagonCompleted = len(dbexecute("SELECT * FROM wagonwheel WHERE studentEmail = ?",(student["email"],)))
        evalCompleted = len(dbexecute("SELECT * FROM studentEvaluation WHERE email = ?",(student["email"],)))
        taskRows = dbexecute("SELECT taskID FROM studentTask WHERE studentEmail = ?",(student["email"],))
        taskList=[]
        for task in taskRows:
            taskList.append(task["taskID"])
        tasksCompleted = len(list(dict.fromkeys(taskList)))
        
        student["completed"] = wagonCompleted+evalCompleted+tasksCompleted


        
    return render_template("teacher.html",students=students,maxAmount=maxAmount)

#user enters email to reset password
@app.route('/forgotPwEmail', methods=['POST', 'GET'])
def forgotPwEmail():
    if request.method == 'POST':
        session["codeCorrect"] = False
        email = request.form.get("email")
        allEmails = dbexecute("SELECT email FROM student;") + dbexecute("SELECT email FROM coach;")
        if email in str(allEmails):
            #generate reset password code and add it to the database 
            resetCode = randint(1000000,9999999)
            dbexecute("INSERT OR REPLACE INTO forgotPassword (email,resetCode,dateCreated) VALUES (?,?,CURRENT_TIMESTAMP)",(email,resetCode))

            # Send the email via gmail's  server, over SSL 
            me = "kaivalya8111@gmail.com"
            my_password = "(ommited)"
            

            msg = MIMEMultipart('alternative')
            msg['Subject'] = "Reset Password Code"
            msg['From'] = me
            msg['To'] = email

            html = '<html><body><p>Your reset password code is '+str(resetCode)+'</p></body></html>'
            part2 = MIMEText(html, 'html')

            msg.attach(part2)

            
            emailsession = smtplib.SMTP_SSL('smtp.gmail.com')

            emailsession.login(me, my_password)

            emailsession.sendmail(me, email, msg.as_string())
            emailsession.quit()

            #save the email for which the password is being reset
            session["resetEmail"] = email

            return render_template("forgotPwCode.html")

        else:
            return render_template("error.html",errorMessage="Invalid email.")
    # return the html page on a GET request
    else:
        return render_template("forgotPwEmail.html")


#route for the password reset code to be entered and verified
@app.route('/forgotPwCode', methods=['POST'])
def forgotPwCode():
    #compare entered code to actual code
    codeEntered = request.form.get("code")
    email = session["resetEmail"]
    actualCode = dbexecute("SELECT resetCode from forgotPassword WHERE email = ?",(email,))
    if len(actualCode) == 0:
        return render_template("error.html",errorMessage="Invalid code")
    #go to the reset password page if the codes match
    if actualCode[0]["resetCode"] == codeEntered:
        session["codeCorrect"] = True
        return render_template("resetpassword.html")
    else:
        return render_template("error.html",errorMessage="Invalid code")


#assuming they entered the correct code, reset password
@app.route('/resetPassword', methods=['POST'])
def resetPassword():
    if not session["codeEntered"]:
        return render_template("error.html",errorMessage="Sorry you can't access this page.")
    pw = hashlib.md5(request.form['password'].encode())
    confirmpw = hashlib.md5(request.form['confirmpw'].encode())

    #validation
    if pw.hexdigest() != confirmpw.hexdigest():
        return render_template("error.html",errorMessage="Passwords not the same/Password must be at least 8 characters")

    #update the password on the database
    studentAccount = len(dbexecute("SELECT * FROM student WHERE email = ?",(session["resetEmail"],))) > 0
    if studentAccount:
        dbexecute("UPDATE student set password = ? WHERE email = ?",(pw.hexdigest(),session["resetEmail"]))
    else:
        dbexecute("UPDATE coach set password = ? WHERE email = ?",(pw.hexdigest(),session["resetEmail"]))
    dbexecute("DELETE FROM forgotPassword WHERE email = ?",(session["resetEmail"],))
    return redirect("/")





@app.route('/matchpairs', methods=['POST', 'GET'])
@login_required
def matchpairs():
    if request.method == 'POST':
        #fill students/coaches with the users seelcted by the teacher
        students,coaches =[],[]
        for key,value in request.form.items():
            if value == "on":
                if key[:3] == "stu":
                    students.append(key[4:])
                else:
                    coaches.append(key[6:])
        #match the students and coaches
        pairs,iteration = match(students,coaches)

        #error checking
        if pairs == 0:
            return("Too many students. Not enough coaches.")
        #insert pairs into database
        for student,coach in pairs.items():
            dbexecute("INSERT INTO pairs (studentEmail,coachEmail,iteration) VALUES(?,?,?)", (student,coach,iteration))

        return redirect(url_for("teacher"))
    #if GET request
    else:
        #select all students and coaches so teacher can select
        sturows = dbexecute("SELECT * FROM student;")
        coachrows = dbexecute("SELECT * FROM coach;")
        if session.get("acc_type") == "teacher":
            print("userid = "+session.get("user_id"))
            return render_template("match.html",sturows=sturows,coachrows=coachrows)
        else:
            return "you aren't a teacher"


@app.route('/uniquecode', methods=['POST', 'GET'])
def uniquecode():
    if request.method == 'POST':
        #redirect to 'show' and pass the uniqueCode entered
        code=request.form.get("code")
        return(redirect("/show/"+code))
    else:
        return render_template("uniquecode.html")


@app.route('/coach')
@login_required
def coach():
    if session.get("acc_type") == "coach":
        superpowerEntered = dbexecute("SELECT superpowerID FROM coach WHERE email = ?",(session["user_id"],))[0]["superpowerID"]
        if not superpowerEntered:
            return render_template("choosesuperpower.html")

        #try to get assigned student's unique code
        try:
            studentUniqueCode = dbexecute("SELECT uniqueCode FROM student,pairs WHERE \
                student.email = pairs.studentEmail AND pairs.coachEmail = ? \
                AND iteration=(SELECT MAX(iteration) FROM pairs);",(session.get("user_id"),))[0]["uniqueCode"]
        #student may not be matched to a student for the current iteration
        except:
            return render_template("error.html",errorMessage="You have not been assigned to a student.")
        #try to select evaluation if written
        try: 
            coachEval = dbexecute("SELECT text FROM coachEvaluation WHERE email = ? AND iteration = (SELECT MAX(iteration) FROM pairs)",(session["user_id"],))[0]["text"]
        except:
            coachEval=""
        
        return render_template("coach.html",uniqueCode=studentUniqueCode,coachEval=coachEval)
    else:
        return render_template("error.html",errorMessage="You are not a coach")
        
            
#show a student's profile if unique code is provided
@app.route('/show/<int:code>')
def show(code):
    #rectified
    #select student's email
    try:
        email = dbexecute("SELECT email from student WHERE uniqueCode=?",(code,))[0]["email"]
    except IndexError:
        return render_template("error.html",errorMessage="Invalid Unique Code")


    # code below is same as student's profile
    tasks = dbexecute("SELECT * FROM task")
    initWagonwheel = dbexecute("SELECT * FROM wagonwheel WHERE studentEmail = ? AND initOrFinal = 0",(email,))[0]
    try:
        finalWagonwheel = dbexecute("SELECT * FROM wagonwheel WHERE studentEmail = ? AND initOrFinal = 1",(email,))[0]
    except:
        finalWagonwheel = {}

    try:
        studenteval= dbexecute("SELECT text FROM studentEvaluation WHERE email = (SELECT email FROM student WHERE uniqueCode = ?)",(code,))[0]["text"]
    except IndexError:
        studenteval = "Evaluation Not Entered Yet."
    
    
    usertasks = dbexecute("SELECT * FROM studentTask WHERE studentEmail = ?",(email,))

    for task in tasks:
        task["text"]= "No Text Entered"
        task["image"] = "No"
        for usertask in usertasks:
            if task["taskID"] == usertask["taskID"]:
                
                task["text"] = usertask["text"]
                if usertask["photo"]!= None:
                    task["image"] = b64encode(usertask["photo"]).decode("utf-8")
           
    #try to select coach's evaluation
    try:
        coacheval = dbexecute("SELECT text FROM coachEvaluation WHERE email = (SELECT coachEmail FROM pairs WHERE \
            studentEmail = (SELECT email FROM student WHERE uniqueCode = ?) and iteration = (SELECT MAX(iteration) \
            FROM pairs)) and iteration = (SELECT MAX(iteration) FROM pairs)",(code,))[0]["text"]
    except IndexError:
        coacheval = "Evaluation Not Entered Yet."

    return render_template("profile.html", initWheel =initWagonwheel,tasks=tasks,finalWheel = finalWagonwheel,studenteval=studenteval,coacheval=coacheval)

          
#register a new user
@app.route('/register', methods=['POST', 'GET'])
def addaccount():
    if request.method == 'POST':
        #clear currently logged in user
        session.clear()

        #get data from HTML form
        fnm = request.form['fnm']
        lnm = request.form['lnm']
        email = request.form['email']
        pw = hashlib.md5(request.form['pw'].encode())
        confirmpw = hashlib.md5(request.form['confirmpw'].encode())
        print(pw.hexdigest(),"\n",confirmpw.hexdigest())
        year = int(request.form['year'])
        acctype = request.form['type']

        #check for dubaicollege email address
        if not re.search('^[A-Za-z]+[0-9][0-9][0-9][0-9]\@dubaicollege.org$',email):
            return render_template("register.html",error="Please use a valid @dubaicollege.org email.")

        #ensure password is entered correctly twice
        if pw.hexdigest() != confirmpw.hexdigest():
            return render_template("register.html",error="Passwords not the same/Password must be at least 8 characters")

        #if student checkbox ticked, insert student data into database
        if acctype == 'student':
            #generate unique code
            unique = randint(10000, 99999)
            currentCodeRows = dbexecute("SELECT uniqueCode FROM student;")
            currentCodes = []
            isCodeUnique = True
            for i in currentCodes:
                currentCodes.append(["uniqueCode"])
            while str(unique) in currentCodes:
                unique = randint(10000, 99999)

            try:
                dbexecute("INSERT INTO student (uniqueCode, firstName,lastName,email,password,yearGroup) VALUES(?,?,?,?,?,?)",
                              (unique, fnm, lnm, email, pw.hexdigest(),year))
            except sqlite3.IntegrityError:
                return render_template("register.html",error="Email already in the system")

                
        else:
            #insert coach info into database
            try:
                dbexecute("INSERT INTO coach (firstName,lastName,email,password,yearGroup) VALUES(?,?,?,?,?)",
                              (fnm, lnm, email, pw.hexdigest(), year))
            except sqlite3.IntegrityError:
                return render_template("register.html",error="Email already in the system")
                
        #set user session
        session["user_id"] = request.form['email']

        #student must fill wagon wheel. Coach must select superpower
        if acctype == "student":
            session["acc_type"] = "student"
            return render_template("fillwheel.html",wagonNum=0)
        else:
            session["acc_type"] = "coach"
            return render_template("choosesuperpower.html")

        return "Error"

    else:
        return render_template("register.html")


@app.route('/choosesuperpower', methods=['POST'])
def choosesuperpower():
    #coach selects a superpower from dropdown
    #database is updated
    chosensp = request.form.get("superpower")
    try:
        powerid = dbexecute(
            "SELECT superpowerID from superpower WHERE superpower = ?", (chosensp,))[0]["superpowerID"]
    except:
        return render_template("choosesuperpower.html",errorMessage="Please choose a superpower.")

    dbexecute("UPDATE coach SET superpowerID = ? WHERE email = ?",
               (powerid, session["user_id"]))

    return redirect(url_for("coach"))



@app.route('/studenteval', methods=['POST'])
def studenteval():
    #get student's evaluation from HTML text field
    evaluation = request.form.get("studenteval")
    if len(evaluation) > 0:
        #check if the student has already written an evaluation
        existingEval = dbexecute("SELECT * FROM studentEvaluation WHERE email = ?",(session["user_id"],))
        if len(existingEval) == 0:
            #if it is the first time insert into database
            dbexecute("INSERT INTO studentEvaluation (email,text) \
                VALUES(?,?)", (session["user_id"], evaluation))
        else:
            #if after the first time, update the database
            dbexecute("UPDATE studentEvaluation SET text=? WHERE email =?",(evaluation,session["user_id"]))

    return redirect("/profile")


@app.route('/coachEvaluation', methods=['POST'])
def coachEval():


    #get coach's evaluation from HTML text field
    evaluation = request.form.get("coacheval")
    if len(evaluation) > 0:
        #sql aggregate function
        #select existing evaluation if it exists
        existingEval = dbexecute("SELECT * FROM coachEvaluation WHERE email = ? AND\
         iteration=(SELECT MAX(iteration) FROM pairs)",(session["user_id"],))
        #if it is the first time insert into database
        if len(existingEval) == 0:
            dbexecute("INSERT INTO coachEvaluation (email,text,iteration) \
                VALUES(?,?,(SELECT MAX(iteration) FROM pairs))", (session["user_id"], evaluation))
        else:
            #if after the first time, update the database
            dbexecute("UPDATE coachEvaluation SET text=? WHERE email =?",(evaluation,session["user_id"]))

    return redirect("/coach")

@app.route('/fillwheel/<int:wagonNum>', methods=['POST'])
@login_required
def fillwheel(wagonNum):
    if wagonNum not in [0,1]:
        return "Error"
    #get wagon wheel data items from respective dropdowns
    try:
        diary = int(request.form.get("diary"))
        time = int(request.form.get("time"))
        packing = int(request.form.get("packing"))
        org = int(request.form.get("org"))
        filing = int(request.form.get("filing"))
        locker = int(request.form.get("locker"))
    except:
        return render_template("fillwheel.html",wagonNum=wagonNum,errorMessage="Please fill all dropdowns.")
    #insert into database
    dbexecute("INSERT OR REPLACE INTO wagonwheel (studentEmail,initOrFinal,timeManagement,filing,\
    	organizationTime,packingBag,hwDiary,lockerUse) VALUES(?,?,?,?,?,?,?,?)", (session["user_id"],wagonNum, time, filing, org, packing, diary, locker))
    


    return redirect("/profile")

@app.route('/fillwheel', methods=['GET'])
@login_required
def fillwheel2():
    return render_template("fillwheel.html",wagonNum=1)

#user uploading images/completing tasks etc.
@app.route('/imageupload', methods=['POST', 'GET'])
@login_required
def imageupload():
    if request.method == 'POST':
        image = None
        #get task text data that has been posted
        for key,value in request.form.items():
            if key[:-1] == "task":
                taskID = int(key[-1])
                tasktext = value
        #get image data that has been posted
        for key,value in request.files.items():
            image = bytearray(value.read())

        #update/insert task data
        
        if image:
            dbexecute("INSERT OR REPLACE INTO studentTask (studentEmail,taskID,submissionTime,text,\
            photo) VALUES(?,?,CURRENT_TIMESTAMP,?,?)", (session["user_id"],taskID,tasktext,image))
        else:
            dbexecute("INSERT OR REPLACE INTO studentTask (studentEmail,taskID,submissionTime,text)\
             VALUES(?,?,CURRENT_TIMESTAMP,?)", (session["user_id"],taskID,tasktext))
        

        return redirect("/profile")
    else:
        return render_template("imageupload.html")


@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect("/")



if __name__ == '__main__':
    app.run(debug=True)