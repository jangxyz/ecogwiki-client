
`ecog` is a python client that talks with [ecogwiki](http://www.ecogwiki.com/). It is configurable to talk with any other ecogwiki hosts.

# Install

You only need the `ecog.py` file, with dependencies: `oauth2`, `feedparser`, `python-dateutil`

Requires python 2.7 or higher.


## `pip` Install

	pip install ecog

This will install `ecog` package together with its dependencies. An runnable `ecog` program is also installed for easy use.


## Manual Install

Download the `ecog.py` file and start using it. Don't forget to install `oauth2`, `feedparser` and `python-dateutil`.


# Getting Started

Try the following commands:

`ecog list`

`ecog cat Home`

`ecog edit Home`

will act on default host, www.ecogwiki.com .

If you have your own host, you can do it on your host:

	ecog --host ecogwiki-jangxyz.appspot.com cat 'ecogwiki client'


## Commands List

* title  - print page titles (think of `ls -1`)
* list   - list wiki pages with simple info (think of `ls -l`)
* recent - list only recent pages
* get PAGE_TITLE  - print metadata of title, in json format
* cat PAGE_TITLE  - print content of title, in markdown format
* edit PAGE_TITLE - open default `EDITOR` to edit and save page
* memo            - short, useful daily memo ;)



# Usage

	$ ecog -h
	usage: ecog [-h] [--auth FILE] [--host HOST] COMMAND ...

	Ecogwiki client

	positional arguments:
	  COMMAND      ecogwiki commands
		cat        print page in markdown
		get        print page in json
		list       list pages info
		title      list all titles
		recent     list recent modified pages
		edit       edit page with editor
		memo       quick memo

	optional arguments:
	  -h, --help   show this help message and exit
	  --auth FILE  auth file storing access token
	  --host HOST  ecogwiki server host

	Information in your fingertips.


NOTE you can use `--host` option to refer to other hosts beside the default `http://www.ecogwiki.com`.
It may be a good idea to alias the default behavior, such as:

	alias ecog='ecog --host ecogwiki-jangxyz.appspot.com'

# Authorization

`ecog` uses OAuth authorization to obtain the access right for the ecogwiki resource. It saves the obtained access token under users acknowledge, so you don't have to do the OAuth dance every time! :)

## Authorization Example

	$ ecog cat some-restricted-content
	access is restricted. Do you want to authorize? (Y/n) y

	Go to the following link in your browser:
	https://ecogwiki-jangxyz.appspot.com/_ah/OAuthAuthorizeToken?oauth_token=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

`<user visits the url with their browser and confirms authorization>`

	Have you authorized me? (y/N) y
	What is the PIN? XXXXXXXXXXXXXXXXXXXXXXXX

	You may now access protected resources using the access tokens above.
	Do you want to save access token for later? (Y/n) y

	USER_CONTENT_SHOWN_HERE


Of course, you don't need to authorize at all if the page is not restricted.


# Commands Description

## title

Prints list of titles for the page.

## list

Print list of pages with additional info. More detailed than [title](#title).

## recent

Show only recently changed files. More brief than [title](#title).

## get 

Show metadata of the page, such as revision, last updated time, acls. The actual body is trimmed for readability.
You can request data for a specific revision of page with `--revision`.

	$ ecog get -h
	usage: ecog get [-h] [--revision REV] TITLE

	positional arguments:
	  TITLE            page title

	optional arguments:
	  -h, --help       show this help message and exit
	  --revision REV   specific revision number
      --format FORMAT  one of [json|html|markdown|atom], json by default

Note other formats are also possible.

## cat

Show actual content of the page. 
You can request data for a specific revision of page with `--revision`.

	$ ecog cat -h
	usage: ecog cat [-h] [--revision REV] TITLE

	positional arguments:
	  TITLE           page title

	optional arguments:
	  -h, --help      show this help message and exit
	  --revision REV  specific revision number

Note this is shorthand for `ecog get --format=markdown`

## edit

Edit a page with system's default editor -- in most of the systems it's default to `vi`.

It works in series of steps as the following:

1. `ecog` first reads the most up-to-date page data.
2. editor is fired so you can edit the file.
3. `ecog` prompts you for a comment message. This can be given in advance with `--comment` option.
4. `ecog` saves the new content to the next revision.

Note unchanged content is not saved.

	$ ecog edit -h
	usage: ecog edit [-h] [--template TEXT] [--comment TEXT] TITLE

	Edit page with your favorite editor ($EDITOR)

	positional arguments:
	  TITLE            page title

	optional arguments:
	  -h, --help       show this help message and exit
	  --template TEXT  text on new file
	  --comment TEXT   edit comment message


You may give a default text to begin with if you are creating a new page with `--template` option.


## append

You can quickly add to a specific page -- no need to do all the readings beforehand.

	$ ecog append -h
	usage: ecog append [-h] [--comment MSG] TITLE [TEXT]

	Quickly append to page

	positional arguments:
	  TITLE          page title
	  TEXT           body text. fires editor if not given

	optional arguments:
	  -h, --help     show this help message and exit
	  --comment MSG  comment message


The body text is optional. If not given, once again the editor will fire open.


## memo

Write a daily memo. `ecog` supports easy-to-write memo system.

Everytime you fire `ecog memo`, it will open a page titled `memo/YYYY-mm-dd` with today's date.

	$ ecog memo -h
	usage: ecog memo [-h] [--comment TEXT]

	Edit your daily memo

	optional arguments:
	  -h, --help      show this help message and exit
	  --comment TEXT  edit comment message


NOTE this is shorthand for `ecog edit memo/YYYY-mm-dd`.


# TODO

* user config files
* print highlighted markdown (+pygmentize)
* auto TAB-completion on titles (bash-completion)
* advanced commands like: `find`, `grep`
* and much more to come..


