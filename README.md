# Gym-Reader
Web scraping program I used for my Gym @ Western University

ABOUT
I found a Western run instagram account that posts hourly info about the gym specifcally the amount of people in it. They account for people who are swimming in the pool to people playing a drop-in sport.
I decided to somehow figure out a way to use this data in my benfit to find the best time to go to the gym (time which is least busiest). Then I found out about web-scrapping

REASON I BUILT THIS
At first I was heavily thinking of doing it manually where I open an excel sheet and plot the numbers seeing how many people are in the gym in the 3rd & 4th floor of the gym. 
But instantly saw that it was gonna be tedious work and at the end most likely wont be useful and also the data most likely reflect the least busiest times since everyone doesnt have a set schedule.
Also by the time I plot all the data of the new set it will be close to end of semester and by then end of school year. So automating it wouldve been better so if atleast my data didnt relate then I
wouldnt have lost alot of time on it

HOW IT WORKS
before beginning the project I wanted to see if it was possible to extract the data from the image. I used easyocr library to check if it will work.
After knowing that getting the data is working and the project can be done I then got working on creating the .csv file so that I can easily graph it.

-- Now the hard Part -- 
the problem I had was figuring out to access instagram so that I can extract the data and add it to the .csv file. (instagram is VERY strict on who can get access)
They didnt have any open source api that can be used so I decided to try instaloader where it sends a request to log in and scrape the user through an account but that was raising alot of bot flags and I always got timed out no matter
how hard I try to make it seem like a human was accessing it.

-- Jumping over the Hurdle --
Claude told me to use playwright and how it works is that it opens a tab loads instagram web and inputs username and password like a human would and then you can do whatever you want.
After coding it and testing it everything was perfect but when it ran it always stopped at the login page so I used command line python FILENAME.py --save-session where I can manually input the username and password and after hitting
enter it saves that action, So every time I run the program it would already have access to the instagram account so all it needed to do was get to the account profile see if there is a new post (incase they missed the hourly post) and if
there is it would scan and extract the info needed from the image and save it to the .csv file.

I have the program running through the schedular using a bat file so that once every hour it would run the program.
