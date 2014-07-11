jira-yaml
=========

For those of us who feel YAML provides a far superior interface to JIRA's web UI.

Setup
-----

Install in develop mode so that you can hack the engine:

    git clone https://github.com/ninowalker/jira-yaml.git
    cd jira-yaml
    python setup.py develop


Usage
------

`jywriter` is a command-line program designed to read a YAML file, interpret, and rewrite the input file with any modifications.

The following document (`foo.yaml`) will create two issues for bob, and a comment to an existing issue:

    - assignee: bob
      issuetype: Story
      project: PROJ
    - key: PROJ-123
      summary: An issue
      +comment: This needs more definition.
    - summary: New task for bob in Foo
      components: Foo
    - summary: New task for bob to integrate Bar and Foo
      components: [Bar, Foo]
.

    $ jywriter foo.yaml

`foo.yaml` will be rewritten with keys of the new issues. If there is an error, any partial changes will be written to the document.


Document Structure
------


### Global Settings and Aliased Fields

The first item in the document defines global field values, and a set of aliases for use in the document - especially useful for custom fields:

    - assignee: bob
      customFields:
        actual: customfield_10501
        customer: customfield_10013
        epicLink: customfield_11000
        epicName: customfield_11001
        expected: customfield_10502
        links: issueLinks
        versions: fixVersions
        points: customfield_10004
      issuetype: Story
      project: PROJ
      reporter: sally
      



### Pulling Issues

Any point after the global settings item, add an entry which defines your search query:

    - search: project = PROJ and status = OPEN and assignee = bob

On the next run, the search will execute and the results will be inserted immediately after the search definition. After processing, the search definition will be ammended with `complete: true`.

Flip `complete` to false, and the search will be reexecuted on the next run. The program will not dedup results.

### Creating Issues

First, every JIRA configuration is different, so you'll need to spend some time getting intimate with your project(s), issue types, and required fields for each. Assuming you've done that, *and setup defaults*, creating an issue is as simple as:

    - summary: As a thing, I want to do something, so that something else will happen.

A more complex example: 

    - summary: As a customer, I want Foo to do Bar.
      assignee: bob
      components: Foo Module
      fixVersions: A_Version
      description: Given a Meow, the Foo needs to bar.

If you manage many things via JIRA, you'll be context switching, and can't use global defaults except for a few. For this, you can specify a manifest - a temporary set of defaults.

#### Example Manifest Usage

    - manifest:
        assignee: mary
        components: Foo
    - summary: ... Mary foo task 1
    - summmary: ... Mary foo task 2
    - manifest:
        assignee: bob
        components: Bar
    - summary: ... Bob Bar task 1
    
Note that manifests are not additive; they are replaced fully as to avoid inheritance hell.

### Adding subtasks

Include the key `subtasks`, with a list of summaries (+ optional `assignee`, otherwise inherited).

    - key: PROJ-123
      summary: As a ...
      assignee: me
      subtasks:
      - summary: Design it.
      - summary: Build it.
      - summary: Document it
        assignee: beth
      - summary: Announce it.
        assignee: sam

### Adding comments

Within an issue with a key:

    - key: PROJ-123
      summary: My issue.
      +comment: This is my comment. Add it to the ticket please.
    
On the next run, the comment will be added and then removed from the current document.
