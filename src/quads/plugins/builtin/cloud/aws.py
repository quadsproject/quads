#!/usr/bin/env python3
"""
AWS Cloud Provider Plugin

Provisions EC2 instances when local bare metal is exhausted.
"""
from typing import List, Optional, Dict, Any
from quads.plugins.interfaces.cloud import CloudPlugin, CloudInstance, InstanceState

import boto3
from botocore.exceptions import ClientError


class AWSPlugin(CloudPlugin):
    """
    AWS EC2 provider for cloud instance provisioning.
    """

    name = "aws"
    version = "1.0.0"
    description = "AWS EC2 cloud provider"
    author = "QUADS Team"

    def initialize(self) -> bool:
        """Initialize AWS boto3 client"""

        self.region = self.config.get("region", "us-east-1")
        self.access_key = self.config.get("access_key")
        self.secret_key = self.config.get("secret_key")
        self.default_image_id = self.config.get("default_ami")
        self.subnet_id = self.config.get("subnet_id")
        self.security_group_ids = self.config.get("security_group_ids", [])
        self.key_name = self.config.get("key_name")

        # Create EC2 client
        try:
            self.ec2_client = boto3.client(
                "ec2",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )

            self.ec2_resource = boto3.resource(
                "ec2",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )

            # Test connection
            self.ec2_client.describe_instances(MaxResults=5)

            self.logger.info(f"AWS provider initialized for region {self.region}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize AWS client: {e}")
            return False

    def shutdown(self) -> None:
        """Cleanup resources"""
        pass

    def health_check(self) -> bool:
        """Check if AWS API is accessible"""
        try:
            self.ec2_client.describe_instances(MaxResults=5)
            return True
        except Exception as e:
            self.logger.error(f"AWS health check failed: {e}")
            return False

    async def get_available_capacity(self, instance_type: Optional[str] = None, region: Optional[str] = None) -> int:
        """
        Get available capacity from AWS.

        AWS doesn't provide a direct API for this, so we check quotas.
        """
        try:
            # Get current running instances
            response = self.ec2_client.describe_instances(
                Filters=[
                    {"Name": "instance-state-name", "Values": ["running", "pending"]},
                    {"Name": "tag:quads_type", "Values": ["cloud_instance"]},
                ]
            )

            current_count = sum(len(r["Instances"]) for r in response["Reservations"])

            # Get vCPU quota (simplified - actual quota checking is complex)
            # For production, use Service Quotas API
            max_instances = self.config.get("max_instances", 100)

            available = max(0, max_instances - current_count)
            self.logger.debug(f"AWS available capacity: {available} (max: {max_instances})")

            return available

        except Exception as e:
            self.logger.error(f"Failed to get AWS capacity: {e}")
            return 0

    async def create_instance(
        self,
        name: str,
        instance_type: str,
        image_id: Optional[str] = None,
        region: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Optional[CloudInstance]:
        """Create an EC2 instance"""
        try:
            ami_id = image_id or self.default_image_id
            if not ami_id:
                self.logger.error("No AMI specified and no default configured")
                return None

            # Prepare tags
            tag_specifications = []
            if tags:
                tag_list = [{"Key": k, "Value": v} for k, v in tags.items()]
                tag_list.append({"Key": "Name", "Value": name})
                tag_specifications = [{"ResourceType": "instance", "Tags": tag_list}]

            # Launch instance
            response = self.ec2_client.run_instances(
                ImageId=ami_id,
                InstanceType=instance_type,
                MinCount=1,
                MaxCount=1,
                KeyName=self.key_name,
                SubnetId=self.subnet_id,
                SecurityGroupIds=self.security_group_ids,
                TagSpecifications=tag_specifications,
            )

            instance_data = response["Instances"][0]
            instance_id = instance_data["InstanceId"]

            self.logger.info(f"Created EC2 instance: {instance_id}")

            # Wait for instance to have IP address
            waiter = self.ec2_client.get_waiter("instance_running")
            waiter.wait(InstanceIds=[instance_id])

            # Get updated instance info
            instance = self.ec2_resource.Instance(instance_id)
            instance.reload()

            # Get pricing (simplified - actual pricing is complex)
            cost_per_hour = self._get_instance_cost(instance_type)

            return CloudInstance(
                instance_id=instance_id,
                provider="aws",
                instance_type=instance_type,
                state=InstanceState.RUNNING,
                public_ip=instance.public_ip_address,
                private_ip=instance.private_ip_address,
                region=self.region,
                cost_per_hour=cost_per_hour,
                metadata={"tags": tags or {}},
            )

        except Exception as e:
            self.logger.error(f"Failed to create EC2 instance: {e}")
            return None

    async def start_instance(self, instance_id: str) -> bool:
        """Start a stopped instance"""
        try:
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            self.logger.info(f"Started EC2 instance: {instance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start instance: {e}")
            return False

    async def stop_instance(self, instance_id: str) -> bool:
        """Stop a running instance"""
        try:
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            self.logger.info(f"Stopped EC2 instance: {instance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop instance: {e}")
            return False

    async def terminate_instance(self, instance_id: str) -> bool:
        """Terminate an instance"""
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            self.logger.info(f"Terminated EC2 instance: {instance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to terminate instance: {e}")
            return False

    async def get_instance(self, instance_id: str) -> Optional[CloudInstance]:
        """Get instance details"""
        try:
            instance = self.ec2_resource.Instance(instance_id)
            instance.reload()

            state_map = {
                "pending": InstanceState.PENDING,
                "running": InstanceState.RUNNING,
                "stopped": InstanceState.STOPPED,
                "terminated": InstanceState.TERMINATED,
            }

            state = state_map.get(instance.state["Name"], InstanceState.ERROR)

            tags = {tag["Key"]: tag["Value"] for tag in (instance.tags or [])}

            return CloudInstance(
                instance_id=instance_id,
                provider="aws",
                instance_type=instance.instance_type,
                state=state,
                public_ip=instance.public_ip_address,
                private_ip=instance.private_ip_address,
                region=self.region,
                cost_per_hour=self._get_instance_cost(instance.instance_type),
                metadata={"tags": tags},
            )

        except Exception as e:
            self.logger.error(f"Failed to get instance {instance_id}: {e}")
            return None

    async def list_instances(
        self, tags: Optional[Dict[str, str]] = None, state: Optional[InstanceState] = None
    ) -> List[CloudInstance]:
        """List instances with optional filtering"""
        try:
            filters = []

            if tags:
                for key, value in tags.items():
                    filters.append({"Name": f"tag:{key}", "Values": [value]})

            if state:
                state_name = state.value
                filters.append({"Name": "instance-state-name", "Values": [state_name]})

            response = self.ec2_client.describe_instances(Filters=filters)

            instances = []
            for reservation in response["Reservations"]:
                for inst_data in reservation["Instances"]:
                    instance = await self.get_instance(inst_data["InstanceId"])
                    if instance:
                        instances.append(instance)

            return instances

        except Exception as e:
            self.logger.error(f"Failed to list instances: {e}")
            return []

    async def get_instance_types(
        self, min_vcpus: Optional[int] = None, min_memory_gb: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get available instance types"""
        # Simplified instance type data
        # In production, use EC2 DescribeInstanceTypes API
        instance_types = [
            {"name": "t3.small", "vcpus": 2, "memory_gb": 2, "cost_per_hour": 0.0208},
            {"name": "t3.medium", "vcpus": 2, "memory_gb": 4, "cost_per_hour": 0.0416},
            {"name": "t3.large", "vcpus": 2, "memory_gb": 8, "cost_per_hour": 0.0832},
            {"name": "m5.large", "vcpus": 2, "memory_gb": 8, "cost_per_hour": 0.096},
            {"name": "m5.xlarge", "vcpus": 4, "memory_gb": 16, "cost_per_hour": 0.192},
            {"name": "c5.large", "vcpus": 2, "memory_gb": 4, "cost_per_hour": 0.085},
        ]

        # Filter by requirements
        if min_vcpus:
            instance_types = [t for t in instance_types if t["vcpus"] >= min_vcpus]
        if min_memory_gb:
            instance_types = [t for t in instance_types if t["memory_gb"] >= min_memory_gb]

        return instance_types

    async def estimate_cost(self, instance_type: str, hours: int, region: Optional[str] = None) -> Dict[str, float]:
        """Estimate cost for running an instance"""
        cost_per_hour = self._get_instance_cost(instance_type)

        compute = cost_per_hour * hours
        storage = 0.10 * hours  # Simplified EBS cost
        network = 0.01 * hours  # Simplified data transfer cost

        return {"compute": compute, "storage": storage, "network": network, "total": compute + storage + network}

    async def validate_quota(self, instance_type: str, count: int = 1) -> bool:
        """Check if quota allows provisioning"""
        available = await self.get_available_capacity(instance_type)
        return available >= count

    def _get_instance_cost(self, instance_type: str) -> float:
        """Get hourly cost for instance type (simplified)"""
        # In production, use AWS Pricing API
        pricing = {
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "t3.large": 0.0832,
            "m5.large": 0.096,
            "m5.xlarge": 0.192,
            "c5.large": 0.085,
        }
        return pricing.get(instance_type, 0.10)  # Default $0.10/hour
