```
        __                                    
       /\ \                                   
 _ __  \_\ \    ____            ___   _____   
/\`'__\/'_` \  /',__\          /'___\/\ '__`\ 
\ \ \//\ \L\ \/\__, `\        /\ \__/\ \ \L\ \
 \ \_\\ \___,_\/\____/        \ \____\\ \ ,__/
  \/_/ \/__,_ /\/___/   _______\/____/ \ \ \/ 
                       /\______\        \ \_\ 
                       \/______/         \/_/ 
```

Copy one RDS instance onto another, even if the destination instance already
exists. This tool was motivated by the need to keep a writable staging instance
up to date with production data on a regular basis, which allows devs to test
migrations before deploying to production.

Unless your database is very small, this tool is typically much faster than
using `pg_dump`, `mysqldump`, or the like.

See [the docstring](rds_cp/rds_cp.py).

## Installing

This package requires Python 3.

```sh
$ pip3 install rds_cp
```

## Example usage

```
$ make install
$ AWS_DEFAULT_REGION=us-west-2 \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=yyy \
  RDSCP_SRC_NAME=prod-read-replica \
  RDSCP_DEST_NAME=staging \
  RDSCP_DEST_INSTANCE_CLASS=db.m3.medium \
  rds_cp
```
or equivalently
```
$ AWS_DEFAULT_REGION=us-west-2 \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=yyy \
  rds_cp --src=prod-read-replica --dest=staging --dest-class=db.m3.medium
```

AWS configuration information may be provided in any way that works with 
`awscli`, e.g. through environment variables or `~/.aws`.

## Recommendations

### Use a read-replica as `SRC`

Per the [AWS
docs](http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateSnapshot.html),
taking snapshots can cause minor service interruption on the underlying RDS
instance: 

> During the backup window, storage I/O may be suspended while your data is
> being backed up and you may experience elevated latency. This I/O suspension
> typically lasts for the duration of the snapshot. This period of I/O
> suspension is shorter for Multi-AZ DB deployments, since the backup is taken
> from the standby, but latency can occur during the backup process.

As a result, it's recommended that you aim this tool at a read-replica of
whatever database you want to copy. Read-replicas are easy to configure through
the AWS console.

### Prime the pump before a first run

If you're running this tool for the first time (or even if a considerable
amount of data has been added since the last run), I recommend manually taking
a snapshot of the SRC database beforehand. This is due to how AWS snapshotting
works; the time taken to perform a snapshot is a function of whether other
snapshots exist which contain a sizable subset of that information. So if you
haven't snapshotted in a while, the first snapshot may take a long time.

As you run `rds_cp` more frequently, e.g. on a cron, the time taken for
each run will reduce due to the shrinking size of the snapshot diff.

If `rds_cp` is run and the time to snapshot exceeds a few minutes, an error
will be thrown. So prime the pump first!

## Testing

Run

```
make test
```

I've also packaged a big honking integration test that does live AWS
setup and teardown. It takes about 15 minutes to run, but it's comprehensive. 

I *highly* recommend running this in an AZ that doesn't contain other 
instances.

```                                              
$ make install
$ AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=y ./tests/integration_tests.py
```
