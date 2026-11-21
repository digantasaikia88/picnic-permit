# PRD: Picnic/Recreational Journey Permit

Version 1.0 · 18 November 2026 (updated 19 November 2026)

## 1. About the service

The Picnic/Recreational Journey Permit is an online service through which a group leader applies for approval of a picnic or recreational journey by road in Assam, and receives a QR-coded permit after approval by the District Commissioner.

The service implements the Transport Department's Standard Operating Procedure "Picnic Journeys by Road: Picnic Season". The SOP requires that no picnic vehicle departs without final approval and a valid, displayed QR code.

**Objective.** Every citizen undertaking a picnic or recreational journey by road returns home safely. The portal supports this by making sure that the vehicle, driver, group and destination are checked by the Transport Department, the Police and the District Administration before the journey.

**What the service delivers**

- A mobile-first application form for the group leader.
- A three-level approval workflow: DTO, origin police station, DC office.
- A QR permit that can be read offline with any QR scanner and verified online without login.
- Recording of violations and cancellation of permits.
- Open reporting of accidents and incidents.
- Dashboards and reports for the workflow offices and for supervising offices.

**Name of the service.** "Picnic/Recreational Journey Permit".

## 2. Scope

The first release covers application, approval, the QR permit, violations, incident reporting, and dashboards. It has no integration with other systems.

| In scope | Out of scope (for now) |
| --- | --- |
| Landing page and application form without login, with OTP only for the undertaking and for corrections | Integration with VAHAN, SARATHI and eChallan |
| Workflow: DTO, origin police station, DC office | Checkpoint mobile app |
| Reject, return for correction, and officer correction at every level | Picnic spot master list, map pin and route capture |
| QR permit readable offline, with open online verification | Road defect reporting and 48-hour rectification by municipal bodies and panchayats |
| Violation recording and permit cancellation | Assamese or other language versions |
| Open accident and incident reporting | Owner confirmation by OTP |
| Dashboards and reports with view-only roles | Sunset-based return time |
| Masters: districts, police stations, DTO mapping, users | Per-passenger consent or OTP |

**Consequences of having no integration**

- Vehicle and driver details are entered by the group leader and self-declared.
- The DTO checks the vehicle in VAHAN and the driver in SARATHI from their own access and records the findings on the portal.
- The portal cannot verify documents or challans instantly. It can only validate what is typed into the form (Section 4).

## 3. Users and roles

Four roles act on an application. Everyone else either views reports or uses the open pages without login.

| Role | Login | What they do |
| --- | --- | --- |
| Group Leader (applicant) | No login | Fills and submits the application, corrects it when returned, tracks status, downloads the QR permit, reports incidents |
| District Transport Officer (DTO), with the Motor Vehicle Inspector | Officer login | Checks the vehicle and driver, inspects the vehicle, then forwards, returns or rejects |
| Origin Police Station | Officer login | Verifies the group and trip, enters the destination police station, then forwards to the DC office, returns or rejects |
| DC Office | Officer login | Gives final approval or rejection. Approval generates the QR permit |
| Viewer: State Transport office, SP office, DC office and other leadership | Officer login, view only | Dashboards and reports within their jurisdiction |
| Enforcement user: any official on enforcement duty, from the Transport Department, the Police, or notified by the District Commissioner | No user ID or password. The enforcement access code of the office they work under, used on mobile, with the official's own mobile verified by OTP | Records a violation against a permit and cancels it |
| State User Management Admin | Admin login | Creates officer user IDs with auto-generated passwords, resets passwords, and manages roles, masters and settings |
| General public | No login | Verifies a QR permit, reads the SOP, reports an accident or incident |

Vehicle owners, drivers, handymen and passengers do not log in. Their details are entered by the group leader.

**Jurisdiction**

- A DTO sees applications whose starting point is in their district.
- A police station acts on applications that name it as the origin police station. It also sees, view only, journeys coming to its area as the destination police station.
- A DC office sees all applications of its district from the moment of submission, and acts on those forwarded by the police.
- Viewers are scoped to the State or to one district.

### 3.1 Applicant access without login

The group leader does not register or log in. From the landing page they go straight to the application form, fill it and submit.

- **OTP at submission.** The SOP requires the undertaking to be accepted through OTP. This one OTP also confirms that the mobile number belongs to the group leader.
- **Status search.** A search by application number is open to anyone. A search by mobile number needs an OTP sent to that number. Search is by application number or group leader's mobile number. The result shows the application number, travel date, current office, working status, and the remarks or reason for a return or rejection.
- **Actions that need OTP.** Correcting a returned application, uploading the inspection certificate, viewing the full application and downloading the permit need an OTP sent to the group leader's mobile. Without this, anyone who knows the mobile number could change another person's application.
- **After the OTP.** The browser stays signed in to that mobile number for 30 minutes, then asks for a new OTP. When the visitor only knows the application number, the OTP goes to the group leader's mobile of that application, shown with only its last two digits.
- **Mobile search with no applications.** The screen says the same thing whether or not the number has applications, and an OTP is sent only when it has, so nobody can test which numbers have applied.
- **No saved drafts.** Entries are kept on the applicant's device between steps until submission. An unfinished form cannot be continued on another device. The one exception is uploaded files: each file is sent to the server when it is chosen, so that a slow connection does not have to carry them all at once, and is deleted after 24 hours if the form is not submitted.

**Assisted filing.** A group leader who finds the form difficult can apply through a Public Facilitation Centre or Common Service Centre. The operator fills the same public form on the leader's behalf, and the OTP still goes to the group leader's mobile, so the undertaking remains the leader's own. Any service charge at the centre is to be decided.

### 3.2 Officer accounts

Officers log in with a user ID and password. Mobile OTP login is not used for officers in this release, because collecting the mobile numbers of all officials in the time available is not practical.

- There are several State User Management Admins, so that user creation and password resets do not wait on one person. A State User Management Admin creates the user IDs for every DTO office, police station, DC office and viewer, each with an auto-generated password.
- The password must be changed at the first login.
- If a password is lost, the State User Management Admin resets it. The portal generates a new password, which the admin shares with the office, and it must again be changed at the next login.
- User IDs can be created in bulk by uploading an Excel or CSV list of offices. The portal returns the list with the generated user IDs and passwords for distribution.
- Passwords follow a minimum strength rule. An account locks for a period after repeated wrong attempts, and the login page has a captcha. The values are in Section 13.4.
- Because an office may share one user ID, the officer enters their name and designation when taking an action, so that the record shows who acted.

**User ID naming**

A user ID is a short role prefix, a dot, and the office name in lowercase without spaces. Login is not case-sensitive.

| User | Format | Examples |
| --- | --- | --- |
| DTO | `dto.<district short name>` | `dto.tinsukia`, `dto.kamrupm` |
| DC office | `dc.<district short name>` | `dc.tinsukia`, `dc.salmara` |
| Police station | `ps.<station name>` | `ps.margherita`, `ps.dispur` |
| State admin | `admin.<number>` | `admin.1` |
| SP office viewer | `sp.<district short name>` | `sp.tinsukia` |
| State Transport office viewer | `transport.state.<number>` | `transport.state.1` |

- **District short name.** Each district has a short name in the district master, used in user IDs. It is the district name without spaces, except for four long names: Kamrup Metropolitan is kamrupm, South Salmara Mankachar is salmara, West Karbi Anglong is westkarbi, and Karbi Anglong is karbi. The admin can edit it.
- **Police stations.** The station name is used without spaces and without the trailing "PS". All 306 station names in the master are unique, so the district is not part of the ID.
- **Name clash.** If a new police station has the same name as an existing one, the district short name is added, for example `ps.lakhipur.cachar`.
- **Second user in an office.** A number is added, for example `dto.tinsukia.2`.
- **Renames.** Users are linked to offices by an internal ID, so the admin can change a user ID after a district or station is renamed.

The first load creates 376 user IDs: 35 DTO, 35 DC office and 306 police station.

- **First passwords.** The first load creates these accounts with no password, so nobody can log in to them yet. A State User Management Admin then chooses "Generate first passwords", and the portal gives one Excel file with the user IDs and passwords for distribution. The file cannot be downloaded again. If it is lost before the officers have logged in, the admin can issue new passwords to the accounts that have never logged in.
- **First admin.** The first State User Management Admin is created by the technical team from the server, and gets a password that must be changed at the first login. Further admins are created from the portal.
- **DC offices.** There is no separate DC office master. A DC office user is linked directly to its district.

## 4. SOP rules and how the portal applies them

Rules the form can check from the data entered are validations, and the form does not allow them to be broken. Rules that depend on the applicant's word are declaration ticks, which the officers then verify.

| SOP rule | Treatment in the portal |
| --- | --- |
| Application at least one week before departure | Validation. The travel date cannot be earlier than 7 days, or later than 90 days, from the date of submission, and must fall within the picnic season set by the State Admin |
| Journey not to begin before 7:00 AM | Validation on departure time |
| Return by 6:00 PM | Validation on return time. Only 6:00 PM is enforced, with no sunset calculation |
| Passengers not to exceed registered seating capacity | Validation. Seating capacity is a mandatory field, and people cannot be added beyond it |
| Destination within 60 minutes; 60 to 90 minutes only with DC's specific approval; over 90 minutes not permitted | The form offers two choices only. A 60 to 90 minute choice flags the application for the DC |
| One picnic spot per trip | The form accepts a single destination |
| Goods vehicles, trucks, tractors and trailers excluded | Not offered in the vehicle type list, plus a declaration tick |
| Vehicle documents valid on the travel date | Declaration tick. DTO verifies |
| Unpaid challans cleared; vehicle with three or more challans not recommended | Declaration tick. DTO verifies |
| Driver: valid licence for the vehicle class, no active suspension | Declaration tick. DTO verifies in SARATHI |
| Driver: no drink-driving or dangerous-driving conviction in the preceding three years | Declaration tick. DTO verifies |
| Driver physically and mentally fit, familiar with the route | Declaration tick |
| Emergency equipment carried | Checklist in the form |
| Undertaking through OTP by the group leader | OTP acceptance before submission |
| Approval specific to vehicle, driver, group, date and route | Any such change after approval needs a fresh application |
| QR code at least 10 cm × 10 cm, displayed on the windscreen | Permit is generated as a printable page of that size |
| Violations recorded on the portal; QR cancelled on violation | Section 9 |
| Accident reported and recorded on the portal within two hours | Section 9 |

## 5. Workflow and statuses

A submitted application goes to the DTO, then the origin police station, then the DC office, and the QR permit is issued on the DC office's approval.

```
Group leader submits
        |
        v
      DTO  ---------------->  Origin police station  ---------------->  DC office  -->  QR permit issued
 (vehicle, driver)              (group and trip)                    (final decision)        |
        |                              |                                   |                v
        +------------------------------+-----------------------------------+      Permit closes: expires after
        |  each office can also:                                                  the travel date, or is
        |    - return to applicant  -> applicant corrects, resubmits to the       cancelled on a violation
        |                              same office
        |    - reject               -> application closed
```

Any of the three offices can return the application to the applicant or reject it. A returned application comes back to the office that returned it.

1. **Submit.** The group leader fills the six steps and submits. The system applies the validations and the duplicate check, then routes the application to the DTO of the origin district.
2. **DTO.** Checks the vehicle and driver, inspects the vehicle, and forwards to the origin police station.
3. **Origin police station.** Verifies the group and trip, enters the destination police station, and forwards to the DC office with checkpoints and comments.
4. **DC office.** Approves or rejects with comments. On approval the QR permit is generated. The applicant gets an SMS and downloads the permit from the portal.
5. **Journey day.** The permit is checked on the road. A violation cancels it.
6. **Closure.** The permit expires at the end of the travel date.

The DC office does not receive the application first, as that would add a step and delay. It sees every application of the district on its dashboard from submission.

| Status | Meaning |
| --- | --- |
| On hold: duplicate claim | Submitted by an applicant who was blocked by the duplicate check and raised a claim. Waiting for the DTO to resolve (Section 10.1) |
| Pending with DTO | Submitted, or resubmitted to the DTO |
| Pending with Police | Forwarded by the DTO |
| Pending with DC Office | Forwarded by the police station |
| Returned to applicant | Sent back for correction by DTO, police or DC office |
| Rejected | Closed by DTO, police or DC office, with reason |
| Approved | QR permit issued and valid |
| Cancelled | Permit cancelled after a violation |
| Expired | Travel date is over |

## 6. Application form

The form is mobile-first, in English only, and split into six steps so that each screen stays short. The applicant opens the form from the landing page and fills it without login. Screen mock-ups: [Picnic Portal – Application Form](https://claude.ai/artifact/V7Hjs3wWjkqTYaat7gYyuK).

### Step 1: Group leader and journey

| Field | Type | Rule |
| --- | --- | --- |
| Full name | Text | Mandatory |
| Age | Number | Mandatory. At least 18 years. Shown beside Gender on one row, directly under the name |
| Gender | Dropdown | Mandatory |
| Mobile number | Mobile | Mandatory. Entered by the group leader and verified by OTP at the undertaking in Step 6 |
| Date of travel | Date | Mandatory. At least 7 days and not more than 90 days from today, and within the picnic season |
| Departure time | Time | Mandatory. Not before 7:00 AM |
| Return time | Time | Mandatory. Not after 6:00 PM, and later than departure |
| Starting point (full address) | Text area | Mandatory |
| District of starting point | Dropdown | Mandatory. Decides the DTO and DC office |
| Police station of starting point | Dropdown, filtered by district | Mandatory. Decides the verifying police station |

### Step 2: Destination

| Field | Type | Rule |
| --- | --- | --- |
| Full address of the picnic spot | Text area | Mandatory. One spot only |
| District | Dropdown | Mandatory |
| Police station | Dropdown, filtered by district | Optional. "Not sure" allowed. The origin police station fills or corrects it |
| Driving time, one way | Choice: up to 60 minutes / 60 to 90 minutes | Mandatory. 60 to 90 minutes flags the application for the DC's specific approval |

### Step 3: Vehicle

| Field | Type | Rule |
| --- | --- | --- |
| Registration number | Text | Mandatory. Stored without spaces, in capitals |
| Type of vehicle | Dropdown from the vehicle type master. Loaded at the start with: car/SUV, maxi cab/traveller, mini bus, bus | Mandatory. No goods vehicle, truck, tractor or trailer. The admin can add or edit types |
| Private or hired | Choice, each with a line of explanation. **Private:** the vehicle belongs to the group leader or someone in the group, such as a family's own car, and is not being paid for. **Hired Transport Vehicle:** the vehicle is taken on hire for the trip, such as a bus, traveller or taxi from an operator, usually with its driver | Mandatory |
| Registered seating capacity | Dropdown, whole numbers from 1 to 100 | Mandatory. Limits the number of people in Step 5 |
| Owner's name | Text | Mandatory |
| Owner's mobile number | Mobile | Mandatory |

Document uploads (PDF or photo, with a size limit):

| Document | Required |
| --- | --- |
| Registration Certificate (RC) | Yes |
| Insurance | Yes |
| Pollution Under Control (PUC) | Yes |
| Vehicle permit | Where required |
| Speed Limiting Device certificate | Where required |
| Fitness and physical inspection certificate for the current year for Picnic/Recreational Journey | If already done |
| Owner's signed self-certificate | Yes. A blank form (PDF) is downloaded from a link beside this upload. The owner fills and signs it by hand, and the applicant scans or photographs it and uploads it |

**If the inspection certificate is not uploaded.** The form shows this note under the upload: "If you do not upload this, the vehicle must be brought to the DTO office for inspection." The application can still be submitted without it. Section 7.1 describes what follows.

Declaration ticks, all mandatory:

- This is not a goods vehicle, truck, tractor or trailer.
- All vehicle documents will be valid on the date of travel.
- There are no unpaid traffic challans on this vehicle.

### Step 4: Driver and handyman

| Field | Type | Rule |
| --- | --- | --- |
| Driver's full name | Text | Mandatory |
| Driving licence number | Text | Mandatory. Stored without spaces, in capitals |
| Vehicle class on the licence | Text | Mandatory |
| Licence valid until | Date | Mandatory. Not earlier than the date of travel |
| Driver's mobile number | Mobile | Mandatory |
| Copy of driving licence | Upload | Mandatory |
| A handyman will travel | Tick | Optional |
| Handyman's name and mobile number | Text, mobile | Mandatory if the tick is selected |

Declaration ticks, all mandatory:

- The licence is valid on the date of travel and is not under suspension.
- The driver has no drink-driving or dangerous-driving conviction in the last three years.
- The driver is physically and mentally fit to drive and knows the route.

### Step 5: Passengers

| Field | Type | Rule |
| --- | --- | --- |
| Full name | Text | Mandatory for each person |
| Age | Number | Mandatory |
| Gender | Dropdown | Mandatory |

- The group leader is added automatically as the first entry, marked "Group leader", with the name, age and gender entered in Step 1, and cannot be removed. To change these the applicant goes back to Step 1. All others are marked "Member".
- Age and gender are not collected for the driver or the handyman.
- The screen shows the list of everyone added, with Edit and Remove on each member.
- A running count shows seats used against the registered seating capacity. The add form closes when the capacity is reached.
- The driver and handyman count towards the seats used.
- Passengers do not give individual consent. The group leader's undertaking covers all members.
- How children are counted is a setting, pending the Transport Department's reply (Section 14).

### Step 6: Emergency kit and undertaking

Emergency kit checklist: stocked first-aid kit, usable spare tyre, vehicle jack, wheel spanner or wrench, fire extinguisher (where available). Every item is mandatory except the fire extinguisher.

Emergency contacts tick: the leader will save 112, 108, the District Police Control Room, the nearest police station, hospital and fire service numbers before departure.

Undertaking by the group leader, accepted by tick and OTP:

- All details and documents given in the application are true.
- The journey will not start until final approval is given and the QR code is displayed on the windscreen.
- Only the listed vehicle, driver and passengers will travel, on the approved date, to the approved destination.
- All members will follow the SOP, and the leader accepts responsibility for safe and disciplined conduct throughout the journey.

A link to the SOP sits above the acceptance tick. On submission the applicant gets an application number and a message that submission is not permission to travel.

## 7. What each office does

Each of the three offices has a work queue and the same four actions: forward (or approve), return to the applicant, correct, and reject. The full application, documents, earlier remarks and the change log are visible at every level. Each office can also set a working status on an application it holds, chosen from the working status master (Section 13.4), which the admin can add to or edit. The working status is shown to the applicant on the status page and in dashboards.

### 7.1 DTO (with the Motor Vehicle Inspector)

The DTO receives every submitted application of the district automatically.

| Task | What is recorded on the portal |
| --- | --- |
| Check the vehicle in VAHAN from the DTO's own access | Result against RC, insurance, PUC, tax, fitness, permit and seating capacity; remarks |
| Check challans on the vehicle | Number unpaid and number on record; remarks |
| Check the driver in SARATHI from the DTO's own access | Licence validity, vehicle class, suspension, convictions; remarks |
| Physical inspection and fitness test, if not already done | Inspection checklist: brakes, steering, all tyres including the spare, lights and indicators, horn, wipers, mirrors, seat belts, doors and emergency exits, Speed Limiting Device; date, inspecting officer, result; inspection certificate upload |
| Verify uploaded documents against the originals | Verified or not, per document |
| Decide | Forward to the origin police station, return to the applicant, or reject with reason |

**Inspection when no certificate was uploaded**

1. The application is marked "Inspection required" in the DTO's queue.
2. The DTO enters the inspection date, time and place. The applicant gets an SMS asking that the vehicle be brought to the DTO office.
3. The MVI inspects the vehicle and records the checklist and the result on the portal.
4. If the vehicle passes, the MVI issues the fitness and physical inspection certificate for the current year for Picnic/Recreational Journey.
5. The certificate is uploaded to the application by the DTO office or by the applicant, whichever is convenient. The DTO office uploads the scan of the certificate in the same "Inspection checklist and result" form in which it records the result as Passed. The scan can also be added later from that form. The applicant has an "Upload inspection certificate" option on the status page, after OTP, while the application is with the DTO. Either way the file shows with the documents of the application.
6. The DTO confirms the uploaded certificate and forwards the application.
7. If the vehicle fails, or is not brought for inspection in time, the DTO returns or rejects the application with the reason.

Inspection status on the application: Certificate uploaded, Inspection required, Inspection scheduled, Passed, Failed.

When the same vehicle is entered in a later application, the DTO sees the certificate already on record for that vehicle, so it need not be inspected again while the certificate is valid.

**Rules the portal applies at the DTO stage**

- The DTO cannot forward until the inspection is recorded as Passed, or the DTO has confirmed an inspection certificate: the one uploaded with the application, or one already on record for the same vehicle. An uploaded certificate alone is not enough.
- A certificate that the DTO office uploads with the inspection result takes the place of any certificate the applicant had uploaded, in the documents of the application as well. It needs no separate confirmation. It is uploaded only for a vehicle that passed.
- When the vehicle was not inspected by the DTO, the DTO may instead accept the certificate the applicant uploaded ("Accept without a new inspection").
- A certificate that the applicant replaces has to be confirmed again.
- The DTO cannot forward until its own tasks are complete: every VAHAN and SARATHI item answered Yes or No (none left "Not checked"), the number of challans unpaid and on record entered, and every document marked Verified or Not verified. The portal lists what is still pending. The inspection certificate needs no separate mark: the inspection rule covers it.
- What the DTO finds does not block by itself. With a "No" or a "Not verified" on record, the DTO still decides whether to forward, return or reject.
- A document that is replaced has to be checked again.
- Three or more unpaid challans show a warning to the DTO. The warning does not block forwarding (Section 14.1).
- The inspection result needs every item of the checklist marked: In order, Not in order, or Does not apply. A vehicle cannot be passed while an item is Not in order.
- The inspection date cannot be in the past when scheduled, nor after the travel date.
- If the vehicle is changed by a correction, the inspection, the certificate confirmation and the findings are cleared. If only the driver is changed, the findings are cleared.

### 7.2 Origin police station

| Task | What is recorded on the portal |
| --- | --- |
| Verify the picnic group and trip details | Verification remarks |
| Enter or update the destination police station (mandatory before forwarding) | Destination police station |
| Confirm the declared driving time | Confirmed, or corrected to the other band |
| Inform the destination police station | Done by the portal once the destination police station is entered: the journey appears in that station's incoming journeys list |
| Note checkpoints and any safety or law-and-order concern | Checkpoints and comments for the DC office |
| Decide | Forward to the DC office, return to the applicant, or reject with reason |

The police station cannot forward until it has saved its verification: the destination police station, the driving time (saving confirms it) and the verification remarks. Checkpoints and comments are optional.

**Wrong origin police station**

If the applicant chose the wrong origin police station, the station that received the application transfers it to the correct one.

1. The station opens the application and chooses "Transfer to another police station".
2. It selects the correct police station of the same district and enters a mandatory remark.
3. The origin police station field is updated and the application moves to the correct station's queue. The status stays "Pending with Police".
4. The transfer is recorded in the change log, and the applicant gets an SMS naming the new station.
5. The receiving station verifies the application as usual. It can transfer again if needed, and the log shows every transfer.

A transfer is limited to police stations of the same district, because the DTO and DC office are decided by the district. A resubmitted application always goes back to the office that returned it. When the starting point is in another district, the office corrects the district and the application moves to that district's DTO (Section 7.4).

The DTO can also correct the origin police station while the application is at the DTO stage, using the normal officer correction.

**Destination police station**

- The origin police station enters or updates the destination police station. This is mandatory before forwarding to the DC office.
- The destination police station then sees the journey in an "Incoming journeys" list on its dashboard, with travel date, vehicle number, number of people, group leader's contact and current status.
- The list is view only. The destination station does not act on the application.
- The list shows the journey from the time the destination station is entered, and marks it Approved, Rejected or Cancelled as the application moves.
- The SP office of the destination district sees the same list for the whole district.

### 7.3 DC office

| Task | What is recorded on the portal |
| --- | --- |
| Review the DTO and police findings | Nothing further |
| Decide 60 to 90 minute cases, which need the DC's specific approval | Specific approval remark |
| Decide | Approve, return to the applicant, or reject, with comments |
| On approval | The system generates the QR permit and tells the applicant by SMS. The applicant downloads it from the status page after OTP |

### 7.4 Rules common to all three levels

- **Reject.** A reason is mandatory. The application closes. The applicant sees the status and reason and gets an SMS. Rejections appear in dashboards by level and reason. There is no appeal in the portal. The applicant may apply afresh.
- **Return to applicant.** Remarks are mandatory. After the applicant corrects and resubmits, the application always comes back to the office that returned it.
- **Who acted.** Several officials may share one office user ID. Every action therefore asks for the official's name and designation, stores them in the change log with the user ID, and remembers them on that computer.
- **Ready reasons.** For a return or a rejection the officer picks a ready reason, writes remarks, or both. The admin can add or edit the ready reasons (Section 13.1).
- **Correct.** An officer of the office that holds the application may edit the data or upload and replace a document directly. The officer may change everything except the group leader's mobile number.
- **Wrong district.** If an officer corrects the district of the starting point, the application moves to the DTO of the new district and starts there.
- **Change log.** Every change stores the user, time, old value and new value. The applicant is notified by SMS of any officer correction.
- **Re-check.** If the vehicle or driver is changed after the DTO stage, the application goes back to the DTO.
- **Validations hold.** The form rules in Section 4 apply to corrected data. The 7 days count from the original submission date.
- **What the applicant can change.** Everything except the group leader's mobile number, because the OTP is tied to it, and the district of the starting point (Section 14.1). Documents stay unless a new file replaces them.
- **Duplicate check on correction.** The application already holds its vehicle and driver for its date. A clash counts only where the correction changes the vehicle, the driver or the date. A duplicate claim on hold against the application does not stop its correction.

### 7.5 Supervising offices

The State Transport office, SP offices, DC offices and other leadership have view-only access to dashboards and reports (Section 12). They do not act on applications.

## 8. QR permit and public verification

On approval the system generates a permit with a QR code that carries the permit details as plain text and a short verification link.

**Plain text in the QR, readable offline with any QR scanner**

- Permit number
- Date of travel and permitted hours
- Vehicle registration number
- Driver's name and licence number
- Number of people travelling
- Starting point and destination
- Group leader's mobile number

**Verification link in the QR**

- Opens a public page with no login.
- Shows the live status: Valid, Cancelled or Expired, with the same details as the QR text.
- Has a search box for permit number or vehicle number, in case a printed QR is damaged.
- Carries links to the SOP and to the incident report form.

**Permit document**

- A printable page with the QR at no less than 10 cm × 10 cm, to be pasted inside the driver's-side windscreen.
- Not sent by SMS. The SMS on approval tells the group leader that the permit is ready. The group leader downloads it from the status page after OTP, prints it, and pastes the QR code on the windscreen.
- Valid only for the approved vehicle, driver, date and destination.
- Expires automatically at the end of the travel date.

**Known limitation.** A QR read offline shows what was printed at approval. It cannot show a later cancellation and cannot by itself prove that it is genuine. The officer compares the text with the vehicle in front of them and uses the link when there is network. The QR text should be kept short so that a 10 cm print scans reliably.

## 9. Violations, cancellation and incident reporting

### 9.1 Violations and cancellation

A violation caught by the police or any authority is recorded on the portal and cancels the QR permit.

- Any official on enforcement duty can record a violation from a phone browser. Such officials may belong to the Transport Department, the Police, or be notified by the District Commissioner.
- There is no enforcement login. The official uses the enforcement access code of the office they work under, and their own mobile number verified by OTP. Office users who record a violation use the same route.
- The officer searches by permit number or vehicle number.
- Fields: type of violation, place, date and time, action taken, remarks.
- Violation types follow the SOP: overcrowding, unregistered passenger, travel outside permitted hours, change of destination or additional stop, drink-driving, missing documents, QR not displayed, other.
- On saving, the permit status becomes Cancelled, the verification page shows Cancelled, and the group leader gets an SMS.
- The record shows in the dashboards of the origin district.

**Cancellation always needs the access code and OTP.** A permit cannot be cancelled by an anonymous user. The verification page is public, so an open cancel option would let anyone cancel another group's permit. Every cancellation must record which official did it and why.

**The enforcement access code**

Officials on enforcement duty work on the road with only a mobile phone, so the whole flow runs in a phone browser. Individual user IDs are not created for them, because their number is large and collecting their details in the time available is not practical.

- **What it is.** A number generated by the portal, one for each DTO office, police station and DC office (Section 13.4). It proves that the official belongs to, or was authorised by, that office. It is not a personal password.
- **Who holds it.** The office's own user sees the code on the office dashboard after logging in. It is created together with the office's account.
- **Who shares it, and with whom.** The head of the office shares it with the officials working under that office.

| Office | Shares its code with |
| --- | --- |
| DTO office | Enforcement Inspectors, Motor Vehicle Inspectors and other Transport Department staff on enforcement duty |
| Police station | The station's own personnel on checkpoint or patrol duty |
| DC office | Officials notified by the District Commissioner for enforcement, such as magistrates and circle officers |

- **First use on a phone.** The official enters the office's access code and their own name, designation and mobile number, and confirms the mobile number by OTP. These details are saved on the phone, so the official does not enter them again. No list of officials has to be collected beforehand, and every cancellation still carries a verified mobile number.
- **On the road.** The official scans the QR with the phone. The verification page opens, and an official who has completed the step above sees a "Record violation" button on it.
- **Limits.** An enforcement user can only verify permits and record violations. They cannot process applications.
- **Changing the code.** The office head can change the code at any time, which ends access for everyone using the old code.

**What is captured for each cancellation**

| Item | Source |
| --- | --- |
| Official's office, name, designation and mobile number | Office from the access code. Name, designation and mobile number as entered by the official and verified by OTP |
| Type of violation | Chosen from the admin's list |
| Reason and remarks | Entered by the official. Mandatory |
| Place | Entered by the official, with the phone's location if permitted |
| Time of violation and time of recording | Entered and automatic |
| Photo | Optional |

A cancellation shows at once on the dashboards of the DTO and the origin police station. If a permit was cancelled wrongly, the DTO or DC office can restore it with a recorded reason. Where there is no network, the permit cannot be cancelled on the spot. The official acts on the vehicle under the SOP and records the violation when back in network. The record then shows both the time of the violation and the later time of recording.

### 9.2 Accident and incident reporting

The group leader, a checkpoint, or anyone else can report an accident or incident through an open form with no login.

| Field | Rule |
| --- | --- |
| Permit number or vehicle number | Mandatory |
| Place | Mandatory |
| Date and time of occurrence | Mandatory |
| Type: accident, injury, breakdown, other emergency | Mandatory |
| Description | Mandatory |
| Photo | Optional |
| Reporter's name and mobile number | Mandatory. Mobile verified by OTP to discourage false reports |

- The form shows 112 and 108 at the top, since the SOP requires calling them immediately.
- The report goes to the origin police station and the DC office and is linked to the permit.
- A report does not cancel the permit by itself. An officer cancels it if a violation is found.
- The form is reachable from the landing page and from the QR verification page.

## 10. Preventing duplicate applications

A journey is identified by its vehicle and driver on a given date, because neither can be on two picnic trips on the same day. Passengers are not used for matching, as the form holds no mobile number or ID for them.

| Check at submission | Action |
| --- | --- |
| Same vehicle registration number on the same travel date | Block, whoever applies |
| Same driving licence number on the same travel date | Block |
| Same group leader mobile on the same date with a different vehicle | Allow, since a large group may need more than one vehicle. Shown to the officers |
| Same vehicle or driver rejected earlier | Allow a fresh application. The earlier rejection and its reason are shown to the officers |

- Registration and licence numbers are compared after removing spaces and hyphens and converting to capitals.
- Only active applications count: submitted, under process, returned for correction, or approved. An unsubmitted form does not hold a slot.
- The blocked applicant sees a message that an application already exists for that vehicle or driver on that date.

### 10.1 Fake or prank applications

Because there is no login, someone could apply using another person's vehicle or driver, and the duplicate check would then block the genuine applicant. The DTO resolves such cases.

**Safeguards at submission**

- Every application is tied to a mobile number verified by OTP, so the person who applied can be traced.
- The owner's signed self-certificate is a mandatory upload.
- A captcha on the form, and a limit on the number of applications one mobile number can submit in a day.

**When a genuine applicant is blocked**

1. The blocked applicant sees that an application already exists for that vehicle or driver on that date, with an option "This is my vehicle or driver: raise a claim".
2. On choosing it, their application is submitted with the status "On hold: duplicate claim". It keeps its own submission date for the 7-day rule.
3. The DTO sees both applications side by side in a "Duplicate claims" list, with the mobile numbers, owner details and uploaded documents of each.
4. The DTO verifies which one is genuine: by checking the registered owner in VAHAN, contacting the owner, and comparing the owner's self-certificate and RC.
5. The DTO rejects the other application with the reason "Not authorised by the vehicle owner or driver". This frees the vehicle and driver for that date.
6. The held application moves to "Pending with DTO" and continues as normal. Both applicants get an SMS.

**After a prank is confirmed**

- The DTO can flag the mobile number that filed it, when accepting a claim, rejecting a claim, or rejecting a fake application. Flagging is the DTO's choice, because a clash can also be an honest mistake. Later applications of a flagged number show a warning to officers.
- A State User Management Admin can block a flagged mobile number from applying, lift the block, or remove the flag.

**How the portal resolves a claim**

- The claim waits with the DTO of its own district. That DTO may reject the blocking application even if it belongs to another district, and sees its details and documents only inside the claim.
- Accepting a claim rejects every active application that blocks it, with the reason "Not authorised by the vehicle owner or driver".
- If the blocking application is already approved, the claim cannot be accepted until that permit is cancelled (Section 9.1).
- If nothing blocks the claim any more, accepting it simply moves it to the DTO's queue.
- The DTO may instead reject the claim itself, with a reason. The other application carries on.
- The DTO can also reject on their own any application they find to be fake, without waiting for a claim.

## 11. Notifications

The group leader gets an SMS at every change of status. Officers see new items in their work queue.

| Event | SMS to the group leader |
| --- | --- |
| Undertaking at submission, and corrections | OTP |
| Application submitted | Application number, with a note that it is not permission to travel |
| Forwarded by DTO or by police | Current stage |
| Returned for correction | Who returned it, and a link to correct |
| Corrected by an officer | What was changed |
| Rejected | Level and reason |
| Approved | Permit number, and a link to the status page, where the permit is downloaded after OTP |
| Permit cancelled | Reason |

When the DTO schedules a vehicle inspection, the group leader also gets an SMS with the date, time and place, and another with the result. SMS templates need DLT registration before go-live.

## 12. Dashboards and reports

Dashboards are available to the workflow offices and to view-only users, each limited to their jurisdiction. All reports can be filtered by date range, district and status, and exported to Excel and PDF.

| Office | Coverage | What they see |
| --- | --- | --- |
| State Transport office | Whole State | All dashboards and reports, with district comparison |
| DC office | Own district | Every application from submission, the stage where each is pending, and days left before travel |
| SP office | Own district | Applications at police stations, journeys coming into the district, violations and incidents |
| DTO | Own district | Own queue, inspection load, rejections |
| Police station | Own station | Own queue, approved journeys starting from the station area, and incoming journeys to the station area as destination |

**Dashboard counts**

- Applications received, pending at DTO, pending at police, pending at DC office, returned to applicant, approved, rejected.
- Applications where the travel date is within 3 days and a decision is still pending.
- Permits valid today, cancelled, expired.
- Violations and incidents reported.

**Reports**

| Report | Use |
| --- | --- |
| Application register | Full list with status, stage and dates |
| Pendency and ageing by stage | Shows where applications are held up against the travel date |
| Rejections by level and reason | Rejections are captured here, as decided |
| Returned for correction | Count, level, and time taken by applicants to resubmit |
| Approved journeys by travel date and destination district | Lets destination police and administration plan |
| 60 to 90 minute cases | Specific approvals given by the DC |
| Violations and cancelled permits | By type, place and district |
| Accident and incident reports | By type and district |
| Processing time | Average days at each level |
| Officer corrections | Change log of edits made by officers |

**Functions on the officer dashboard**

- **Search** by application number, vehicle number or mobile number.
- **Queue sorted by travel date**, showing days left and highlighting applications close to the date.
- **Alerts on an application**: the same vehicle, driver or group leader in other applications, earlier rejections, and flagged mobile numbers. A duplicate for the same vehicle or driver on the same date cannot be submitted (Section 10).
- **Application timeline**: who did what and when, including officer corrections and transfers.
- **Daily list of approved journeys**: a printable list by travel date for checkpoints, for use where there is no network.
- **Ready remarks**: reasons for return and rejection chosen from a list that the admin maintains, with room for a free-text remark.
- **Print or download** an application as PDF for the office file.

## 13. Administration and quality requirements

### 13.1 Master data and settings

| Master or setting | Purpose |
| --- | --- |
| Districts | Routing and jurisdiction |
| Police stations by district | Origin and destination dropdowns, police routing |
| District to DTO and DC office mapping | Automatic routing on submission |
| Users and roles | Officer, viewer and administrator accounts with jurisdiction |
| Vehicle types | Dropdown in Step 3. Loaded at the start with four types. The admin can add or edit |
| Working statuses | Offered to the three offices (Section 7), each office seeing only its own. Loaded at the start with the list in Section 13.4. The admin can add or edit a status and choose its offices |
| Violation types, and reasons for return and rejection | Entered by the admin and offered to officers as ready remarks, so that reports stay uniform |
| Season dates | Start date and end date of the picnic season, set by the State Admin. The date of travel must fall within the season. Until the dates are set, there is no season limit |
| Minimum days before travel, permitted hours | Kept as settings (7 days, 7:00 AM, 6:00 PM) so that an SOP amendment needs no code change |
| Child counting rule | Setting, pending the Transport Department's decision |
| SOP document | Published on the public pages |
| District emergency contacts | A list the admin maintains: district, name of the service, phone number. Shown on the public Emergency contacts page, with 112 and 108 always at the top |

**District and police station lists received (19 November 2026)**

Two CSV files have been provided and are the source for these masters: District_IDs.csv (35 districts, each with a District ID) and Police_Stations.csv (312 rows: police station name, District ID, office phone number, pincode).

- **Dropdowns.** The district dropdowns use the district list. The origin and destination police station dropdowns show the police stations of the selected district, matched on District ID.
- **Official user IDs.** One police station user ID is created for each police station in this list, in bulk (Section 3.2). Each police station, DTO office and DC office also gets its enforcement access code (Section 9.1).
- **Station code.** The file has no unique ID for a police station. The portal assigns one to each station, so that a station can be renamed or moved without breaking records.

Corrections applied to the police station file, as decided:

| Correction | Rows |
| --- | --- |
| Placed under Tinsukia (District ID was blank) | Saikhowa Ghat PS, Dholla PS, Cheng Chup Chariali PS, Sadiya PS |
| Kept under one district only, and the entry under the other district removed | Lakhipur PS under Goalpara (not Cachar), Jamuguri PS under Sonitpur (not Golaghat), Joypur PS under Dibrugarh (not Cachar), Amguri PS under Sivasagar (not Chirang) |
| Removed | The "Unknown" row, and the second Bokakhat PS row |
| Renamed | "Goalpara RPS" to "Goalpara PS", with the user ID `ps.goalpara` |
| Not used | Office phone number and pincode columns |

The cleaned list has 306 police stations across 35 districts, each with a District ID and a unique name. Only the police station name and District ID are loaded.

The district master has 35 districts, each with a unique District ID, name and short name. The short name is used to build user IDs (Section 3.2).

The cleaned files are in `docs/masters/`: `District_Master.csv`, `Police_Stations_master.csv`, `DTO_Office_Master.csv` and `User_ID_List.csv`.

**Maintaining the district and police station masters**

A State User Management Admin can add or modify districts and police stations from the admin screen, so that a missing district or police station can be put in without a code change.

- **Add a district:** District ID and district name. The ID and the name must each be unique.
- **Add a police station:** name and district. The name must be unique within the district.
- **Modify:** rename a district or police station, or move a police station to another district.
- **Deactivate, not delete:** an entry that has been used in an application cannot be deleted. It can be made inactive, which removes it from the dropdowns and keeps old records intact.
- **New police station:** on adding one, the admin is prompted to create its user ID and enforcement access code.
- **New district:** on adding one, the admin maps its DTO office and DC office, so that applications from it can be routed.
- **Moving a police station:** applications already pending with that station stay with it. New applications follow the new district.
- **Bulk upload:** the same Excel or CSV format can be uploaded to add several entries at once.
- **Change log:** every addition and change records the admin and the time.

**DTO office master (draft)**

A draft DTO office master has been prepared with one DTO office for each of the 35 districts. Each entry has a DTO Office ID ("DTO-" followed by the District ID), the office name, and its district. An application is routed to the DTO office of the starting point's district, and one DTO user ID is created per office.

The draft assumes one DTO office per district. The Transport Department is to confirm the actual list, in particular whether any district has no DTO office of its own or has more than one. The admin can add or modify DTO offices in the same way as police stations.

### 13.2 Public pages

The landing page is designed around the picnic season in Assam. It carries, without login: application status search by application number or group leader's mobile number, the SOP as a PDF with a short "rules at a glance" summary, the apply button, permit verification, incident reporting, and the emergency helplines 112 and 108.

### 13.3 Quality requirements

- **Mobile-first.** The citizen side is designed for phone screens first and works on common mobile browsers and slow connections. Officer screens work on desktop and phone.
- **Language.** English only.
- **Peak load.** Usage will concentrate in the picnic season, around weekends and the New Year. The portal should be load-tested for that peak before go-live.
- **Access control.** Role-based access with jurisdiction limits. Officer accounts are created by the administrator only.
- **Public page protection.** OTP rate limits, and a captcha on the verification search and the incident form.
- **Audit trail.** Every action and data change is logged with user and time, and cannot be edited.
- **Uploads.** PDF, JPG and PNG only, with a size limit per file. No virus scan in this release.
- **No drafts.** Entries are kept on the applicant's device between steps until submission. Nothing is saved on the server before submission, except uploaded files, which are deleted after 24 hours if the form is not submitted.
- **Availability and backup.** Daily backups, and no planned downtime during the season.

### 13.4 Starting values

These are the values loaded at the start. All numbers are whole numbers. The admin can change the settings and the two lists without a code change.

| Item | Starting value |
| --- | --- |
| Application number | 11 digits: 2-digit year, 4-digit District ID of the starting point, 5-digit serial for that district and year. Example: 26102200042 |
| Permit number | The same number as the application, so the applicant keeps one number |
| Enforcement access code | 8 digits |
| Upload size limit | 5 MB per file. The browser compresses photos before upload |
| OTP | 6 digits, valid for 5 minutes, 3 wrong attempts allowed |
| OTP resend | After 60 seconds, and no more than 5 OTPs to one mobile number in 1 hour |
| Applications from one mobile number | 3 in a day |
| Officer account lock | After 5 wrong passwords in a row, locked for 15 minutes |
| Officer login session | 48 hours, with or without activity. Then the officer logs in again |
| Login captcha | A picture of 5 letters and digits, generated by the portal itself with no outside service. Valid for 5 minutes and for one attempt |
| Password rule | At least 8 characters, with at least 1 letter and 1 digit, and not the same as the user ID |
| Auto-generated password | 10 characters |
| Minimum days before travel | 7. Submission on the 1st allows travel on the 8th or any later date |
| Maximum days before travel | 90. A journey more than 90 days ahead cannot be applied for |
| Permitted hours | Departure from 7:00 AM, return by 6:00 PM. Kept as whole hours |
| Group leader's minimum age | 18 years |
| Child counting | Every person counts as one seat. The setting is an age below which a child is not counted, starting at 0 |
| Unsubmitted uploads | Deleted after 24 hours |
| Applicant session on the status page | 30 minutes after the OTP |
| Status search by application number | No captcha. At most 60 searches in 1 hour from one address |

**Vehicle types:** car/SUV, maxi cab/traveller, mini bus, bus.

**Working statuses**

Each office is offered only the working statuses meant for it, and cannot set any other. The admin chooses the offices of each status, and at least one office must be chosen.

| Working status | Offered to |
| --- | --- |
| Received | All three offices. Set automatically when an application arrives |
| Document verification in progress | DTO |
| Awaiting documents from applicant | DTO |
| Inspection scheduled | DTO |
| Inspection completed | DTO |
| Verification in progress | Police station |
| Field verification scheduled | Police station |
| Under review | DC office |
| Put up for approval | All three offices |

## 14. Open points and later phases

### 14.1 Open points for the Transport Department

- [ ] **Children.** Does a child need a full seat, or may a child sit on a parent's lap? If children are counted differently, what is the age cut-off?
- [ ] **Who needs a permit.** The SOP covers private and hired vehicles "carrying groups". Does a family in its own car need a permit?
- [ ] **Seat count.** Do the driver and handyman count towards the registered seating capacity? This document assumes yes.
- [ ] **Challans.** "Three or more challans on record": over what period, and do paid challans count? Until this is decided, the portal warns the DTO at three or more unpaid challans and does not block.
- [ ] **Inspection.** Is the "current year" fitness and physical inspection certificate valid for the whole season, so that a vehicle is inspected once? Is any fee charged for the inspection, and must the vehicle come to the DTO office in every case?
- [ ] **Season.** The State Admin sets the start and end dates in the portal. The dates themselves are still to be given by the department.
- [ ] **Group leader as driver.** The form counts the driver as a separate person. If the group leader or a member drives the vehicle, that person is counted twice against the seats. Should the form ask whether the driver is one of the group?
- [ ] **Inter-district journeys.** This document assumes the origin district's DTO, police station and DC office process the application.
- [x] **Destination police.** Decided: the destination police station sees incoming journeys on its dashboard (Section 7.2).
- [ ] **Passenger changes after approval.** Does a changed passenger need a fresh application?
- [x] **Group leader details.** Decided: age and gender of the group leader are collected in Step 1.
- [x] **Wrong district.** Decided: the applicant cannot change the district of the starting point, but any office that holds the application can correct it. The application then moves to the DTO of the new district (Section 7.4).
- [ ] **Fee.** This document assumes no fee.

### 14.2 Later phases

| Item | Benefit |
| --- | --- |
| VAHAN, SARATHI and eChallan integration | Instant checks at submission and less manual work for the DTO |
| Checkpoint mobile app | Faster scanning and violation entry, with offline sync |
| Assamese and other languages | Wider reach |
| Picnic spot master with location | Uniform destinations and driving-time calculation |
| Sunset-based return time | Closer match to the SOP's "before sunset" rule |
| Road defect reporting for municipal bodies and panchayats | Covers Section 3.8 of the SOP |
