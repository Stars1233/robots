### Fixed: the AWS example refuses an S3 bucket another account owns

`examples/isaac_on_aws/run_smoke.sh` derived its bucket name from the account id
and the region - `strands-isaac-example-$ACCOUNT-$REGION` - and then probed it with
a bare `aws s3api head-bucket`. S3 bucket names are one global namespace and
account ids are not secrets: they appear in ARNs, in error messages and in shared
CloudTrail. So a stranger could pre-create that exact name with a policy granting
the operator access, and `head-bucket` would answer 200 for a bucket *they* owned.

The rest of the pipeline then proceeded into it. The upload handed over the whole
packed working tree including uncommitted changes, and - worse - the presigned URL
embedded in the SSM staging document pointed into their bucket, which root on the
provisioned instance fetches, untars into `/opt/strands` and executes as
`inner.sh` inside the GPU container. That is the same
command-injection-into-a-root-channel the `$WORKDIR` change closed on this
pipeline's local-filesystem leg, reached over S3 instead.

Both S3 legs now assert `--expected-bucket-owner "$ACCOUNT"`. The check alone would
leave a window - a bucket appearing between the probe and the upload would be
written to unchecked - which is why the upload asserts it too, and that forces
`s3api put-object` in place of `s3 cp`: `ExpectedBucketOwner` is modelled on the
`s3api` operations (`HeadBucket`, `PutObject`, `GetObject`) and does not exist on
the high-level `s3` commands. `create-bucket` does not model it and needs it least,
since it fails outright when the name is taken.

The download leg needs no flag of its own: both legs above establish that the
bucket is ours, and a bucket `s3 mb` has just created is private, so no third party
can substitute the object between the upload and the instance's fetch.

When the name is neither ownable nor creatable the script now stops and says why,
rather than falling through to the upload. A raw `BucketAlreadyExists` reads as a
transient AWS problem and invites a retry that cannot succeed, so the refusal names
the real cause and the remedy - `BUCKET` is now overridable for exactly that,
because a globally-unique name held by someone else can only be fixed by choosing
a different one.
