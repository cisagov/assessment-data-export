# assessment-data-export 🚀 #

[![Total alerts](https://img.shields.io/lgtm/alerts/g/cisagov/assessment-data-export.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/cisagov/assessment-data-export/alerts/)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/cisagov/assessment-data-export.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/cisagov/assessment-data-export/context:python)

`assessment-data-export` contains code to export assessment data from a Jira
server and upload that data to an AWS S3 bucket as a JSON file.

Our terraform code to create the S3 bucket can be found in
[https://github.com/cisagov/assessment-data-import-terraform](https://github.com/cisagov/assessment-data-import-terraform)

## Usage ##

To run this script, you first must create a file with the credentials
needed to access your Jira server.  It's a best practice to use a dedicated
Jira account that has only the permissions needed to access the data to be
exported.  The Jira credentials file has the following simple format:

```bash
my_jira_username
my_jira_password
```

Issue the following command to run the script:

```bash
src/ade/assessment_data_export.py --jira-base-url=https://my-jira-server
--jira-credentials-file=my_jira_creds.txt --jira-filter=12345
--s3-bucket=my-bucket --output-filename=assessment-data.json
```

To get help information on the command line arguments, run:

```bash
./assessment_data_export.py -h
```

## Contributing ##

We welcome contributions!  Please see [here](CONTRIBUTING.md) for
details.

## License ##

This project is in the worldwide [public domain](LICENSE.md).

This project is in the public domain within the United States, and
copyright and related rights in the work worldwide are waived through
the [CC0 1.0 Universal public domain
dedication](https://creativecommons.org/publicdomain/zero/1.0/).

All contributions to this project will be released under the CC0
dedication. By submitting a pull request, you are agreeing to comply
with this waiver of copyright interest.
