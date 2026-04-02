gcloud compute instances create mlflow-server \
 --zone=us-central1-a \
 --machine-type=e2-small \
 --image-family=ubuntu-2204-lts \
 --image-project=ubuntu-os-cloud \
 --boot-disk-size=20GB \
 --tags=mlflow-server

gcloud compute instances list

gcloud compute firewall-rules create allow-mlflow \
 --allow=tcp:5000 \
 --target-tags=mlflow-server \
 --description="Allow MLflow server traffic"

commands = "
sudo apt update -y && \
sudo apt upgrade -y && \
sudo apt install python3-pip python3-venv -y
mkdir -p ~/mlflow-data/artifacts

"

gcloud compute ssh mlflow-server --zone=us-central1-a --command="$commands"

gcloud compute instances list
gcloud config set account YOUR_EMAIL
gcloud auth login
