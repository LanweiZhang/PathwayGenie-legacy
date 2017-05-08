# PartsGenie

To run on Google Compute Engine:

1. Create instance from client:

gcloud compute instances create instance-1 --image-family gci-stable --image-project google-containers --zone europe-west1-b --machine-type n1-standard-1

2. Set External IP to static.

3. Firewalls: Allow HTTP traffic.

4. SSH into instance (from GCE console).

5. Clone repository:

git clone https://github.com/neilswainston/PartsGenie.git

6. Move into PartsGenie directory:

cd PartsGenie

7. Run start_server script:

bash start_server.sh
