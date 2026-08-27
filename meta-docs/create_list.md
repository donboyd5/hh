
# Introduction

I want you to create a specialized potential donor mailing list for Hubbard Hall using information from multiple sources. It won't be perfect the first time so we need this to be something that we can automate and improve based on back-and-forth discussion. 

# End Result

The end result will need at least the following fields:

- One or more neon codes that uniquely identify the donor household if the household is in neon 
- A code in the same field or possibly a separate field that gives a made-up code that we create for new households not in the NEON database. The code might be as simple as NEW1, NEW2, NEW3, etc. Lower case. 

- Several indicator fields that indicate what type of household this might be. These are indicators we will create. They include or should include possibilities such as:
- new household
- never donated
- donated last year
- didn't donate in any of the last five years
- and possibly more to be determined

- Additional indicator codes or values indicating what sort of engagement the household has with hubbard hall. For example it might be:
- how much money they spent on art performances, including events, in the last three years
- how much money they spent on glasses in the last three years
- one or two other categories

- We probably also need a single indicator variable that is text that says, in a single word or set of words, their predominant form of engagement. It might be:
- arts, which includes performances and events and films and things like that
- classes
- both
- none

We'll need simple codes to indicate whether they have


- In addition to these fields we will need suitable mailing list fields:
- Last name
- First name of the household contact
- Household salutation
- Street address
- Phone
- Email
- A code from the database, if one exists, that says whether the person should not be contacted. 
We may also need you to geocode the address and calculate the distance to the hover hall building.

- note fields that may be in neon that say something about the household
We'll also include hand-provided notes

We'll need a "steward" field indicating who, if anyone, we would like to be the steward for a potential donor. In some of the files this might now be named Ambassador or board\_member -- use the name steward instead in the final database


# Sources and methods

Wherever possible we want the data to come from the Neon database. However for people who aren't in the database we will need to do some internet searching. We want the contact information but we will not contact people who are not yet in the database in any automated way. We may try to reach out to them individually in an appropriate manner. 

I have several files that give households and certain note fields. You will use them to help identify neon households to include, and to get the hand-developed note fields in them, but the remainder of data, in theory, should be in and obtained from neon.

Here is a list of the kinds of households to include in the data, followed by a parenthetical indicating whether I think they are in neon. When in neon, you should try go get all info from neon

- households that have donated, above a de minimis amount, in the last 5 years (neon, see 1.HH donor last 3 years wo Board_djb.xlsx -- this has hand-developed note fields (Ambassador, and notes) for people who donated in the last 3 years which we will want to include as steward and notes; we want to expand this to the last 5 years; you can also use it as a check on calculations you do for donations and spending)
- new households recently entered into neon (neon, see New Accounts 25-26 for AF Mailing.xlsx)
- households we appealed to last year who donated (neon, hh-donor-workbook_djb.xlsx, donors sheet, appealed=TRUE, responded=TRUE; include the note field)
- selected households we appealed to last year who did NOT respond (neon, hh-donor-workbook_djb.xlsx, silent-1000plus sheet, those where the household value is bolded -- combine the note and action fields into a single note field)
- people on the Fort Salem Theater list who are NOT in our neon database (EXTERNAL, https://www.fortsalem.com/our-sponsors, people listed in the (individual, non-corporate) sponsor categories for years going back to 2020; we'll need a fst indicator for this; you'll need to find contact information if possible -- look at the web; we'll have to discuss who to keep in our database and who to drop
- ADDITIONAL PEOPLE we have identified - in a separate spreadsheet, to come, possibly not in neon

# Next steps

- first, make sure you understand rules of the repo in meta-docs/RULES.md -- and be prepared to add to or modify those rules as we learn in this project
- make a plan, ask me questions as needed
- update the pulled data from neon
- proceed -- I think the basic approach will be to read the spreadsheets to determine who to include, and if they are in neon, get the data from neon, set the text fields and indicators based on the spreadsheets, and do some calculations to get important values - donations in each of last 5 years, total donations last 5 years, plus spending on arts/events, and classes

