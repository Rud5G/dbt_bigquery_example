# -*- coding: utf-8 -*-
#!/usr/bin/env python3

from google.cloud import bigquery, logging
import os
from optparse import OptionParser
from google.cloud.exceptions import NotFound, Conflict


# TODO: (developer)-update this based on testing needs
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "bigquery-logs-writer-key.json"


class export_logs_utility:
    def __init__(
        self, sink_name, project_id, dataset_name, dataset_location, operation
    ):
        self.sink_name = sink_name
        self.project_id = project_id
        # setup bigquery config
        self.dataset_name = dataset_name
        self.bigquery_client = bigquery.Client(self.project_id)
        self.dataset = self.bigquery_client.dataset(self.dataset_name)
        self.dataset_location = dataset_location
        self.operation = operation
        # https://cloud.google.com/bigquery/docs/reference/auditlogs#auditdata_examples
        # TODO: update for query runs AND dbt jobs
        self.filter_ = r'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.BigQueryAuditMetadata"'

    def operation_sink(self):
        """Main handler that generates or creates sink end to end
        """
        if self.operation == "create":
            self.create_bigquery_dataset()
            self.create_sink()
        elif self.operation == "list":
            self.list_sinks()
        elif self.operation == "update":
            self.update_sink()
        elif self.operation == "delete":
            # do NOT delete dataset and tables in case they need to remain for audit purposes
            self.delete_sink()

    def list_sinks(self):
        """Lists all sinks."""
        logging_client = logging.Client()

        sinks = list(logging_client.list_sinks())

        if not sinks:
            print("No sinks.")

        for sink in sinks:
            print("{}: {} -> {}".format(sink.name, sink.filter_, sink.destination))

    def create_bigquery_dataset(self):
        """Create an empty dataset"""
        try:
            # Specify the geographic location where the dataset should reside.
            self.dataset.location = self.dataset_location
            # Send the dataset to the API for creation.
            # Raises google.api_core.exceptions.Conflict if the Dataset already
            # exists within the project.
            dataset = self.bigquery_client.create_dataset(
                self.dataset
            )  # Make an API request.
            print(
                "Created dataset {}.{}".format(
                    self.bigquery_client.project, dataset.dataset_id
                )
            )
        except Conflict:
            print("Dataset already exists '{}'.".format(self.dataset_name))

    def create_sink(self):
        """Creates a sink to export logs to the given Cloud Storage bucket.

        The filter determines which logs this sink matches and will be exported
        to the destination. For example a filter of 'severity>=INFO' will send
        all logs that have a severity of INFO or greater to the destination.
        See https://cloud.google.com/logging/docs/view/advanced_filters for more
        filter information.
        """
        logging_client = logging.Client()

        # The destination can be a Cloud Storage bucket, a Cloud Pub/Sub topic,
        # or a BigQuery dataset. In this case, it is a Cloud Storage Bucket.
        # See https://cloud.google.com/logging/docs/api/tasks/exporting-logs for
        # information on the destination format.
        destination = f"bigquery.googleapis.com/projects/{self.project_id}/datasets/{self.dataset_name}"

        sink = logging_client.sink(self.sink_name, self.filter_, destination)

        if sink.exists():
            print("Sink {} already exists.".format(sink.name))
            return

        sink.create(unique_writer_identity=True)
        print("Created sink {}".format(sink.name))

    def update_sink(self):
        """Changes a sink's filter.

        The filter determines which logs this sink matches and will be exported
        to the destination. For example a filter of 'severity>=INFO' will send
        all logs that have a severity of INFO or greater to the destination.
        See https://cloud.google.com/logging/docs/view/advanced_filters for more
        filter information.
        """
        logging_client = logging.Client()
        sink = logging_client.sink(self.sink_name)

        sink.reload()

        sink.filter_ = self.filter_
        print("Updated sink {}".format(sink.name))
        sink.update()

    def delete_sink(self):
        """Deletes a sink."""
        logging_client = logging.Client()
        sink = logging_client.sink(self.sink_name)

        sink.delete()

        print("Deleted sink {}".format(sink.name))


if __name__ == "__main__":
    use = "Usage: %prog -s sink_name -p project_id -d dataset_name -l dataset_location -o operation"
    parser = OptionParser(usage=use)
    parser.add_option(
        "-s",
        "--sink_name",
        action="store",
        type="string",
        dest="sink_name",
        help="name of sink for exporting logs",
    )
    parser.add_option(
        "-p",
        "--project_id",
        action="store",
        type="string",
        dest="project_id",
        help="name of Google Cloud project that will create the export logs",
    )
    parser.add_option(
        "-d",
        "--dataset_name",
        action="store",
        type="string",
        dest="dataset_name",
        help="Name of dataset to create or already existing to store exported logs",
    )
    parser.add_option(
        "-l",
        "--dataset_location",
        action="store",
        type="string",
        dest="dataset_location",
        help="Location of dataset to create to store exported logs",
    )
    parser.add_option(
        "-o",
        "--operation",
        action="store",
        type="string",
        dest="operation",
        help="Whether to create or delete the sink",
    )

    (options, args) = parser.parse_args()

    if not options.sink_name:
        parser.error("sink_name not given")

    if not options.project_id:
        parser.error("project_id not given")

    if not options.dataset_name:
        parser.error("dataset_name not given")

    if not options.dataset_location:
        parser.error("dataset_location not given")

    if not options.operation:
        parser.error("operation not given")

    if options.operation not in ("create", "delete", "list", "update"):
        parser.error("operation not compliant to options: create, delete, list, update")

    sink_name = options.sink_name
    project_id = options.project_id
    dataset_name = options.dataset_name
    dataset_location = options.dataset_location
    operation = options.operation

    # define the class utility and run the script
    logs_operator = export_logs_utility(
        sink_name, project_id, dataset_name, dataset_location, operation
    )

    # perform log operation based on operation flag
    logs_operator.operation_sink()