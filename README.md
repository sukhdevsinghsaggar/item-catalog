# Item Catalog
This is a python module that creates a website and JSON API for a list of items grouped into a category. Users can edit or delete items they've creating. Adding items, deleteing items and editing items requiring logging in with Google+ or Facebook.

## Instructions to run Project:
# Setup The database and starting the server:

1. In the root directory run Git Bash / Terminal
2. Run "pyhon database_setup.py" this will create the database with the categories defined in that script.
3. Populate the database using "python lotsofmenus.py"
4. Run "python project.py" to start the server.

## Start using the website by typing http://localhost:5000/ in browser


## How did I set up a Google Plus auth application -
1. Go to https://console.developers.google.com/project and login with Google.
2. Create a new project
3. Name the project
4. Select "API's and Auth-> Credentials-> Create a new OAuth client ID" from the project menu
5. Select Web Application
6. On the consent screen, type in a product name and save.
7. In Authorized javascript origins add: http://0.0.0.0:5000 http://localhost:5000
8. Click create client ID
9. Click download JSON and save it into the root director of this project.
10. Rename the JSON file "client_secret.json"
