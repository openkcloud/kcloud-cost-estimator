"""
Kepler Client - Kepler metrics collection via Prometheus API
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from .metrics import KeplerMetrics
from .models import PowerData, ContainerPowerData, NodePowerData

logger = logging.getLogger(__name__)

class KeplerClient:
    """Kepler Prometheus metrics collection client"""
    
    def __init__(self, prometheus_url: str, metrics_interval: str = "30s"):
        """
        Initialize Kepler client
        
        Args:
            prometheus_url: Prometheus server URL
            metrics_interval: Metrics collection interval
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.metrics_interval = metrics_interval
        self.session = None
        
        # Load Kepler metrics definitions
        self.metrics = KeplerMetrics()
        
        logger.info(f"KeplerClient initialized: {prometheus_url}")
    
    async def __aenter__(self):
        """Enter async context manager"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager"""
        await self.close()
    
    async def _ensure_session(self):
        """Create HTTP session"""
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Kepler/Prometheus connection status"""
        try:
            await self._ensure_session()
            
            # Check Prometheus status
            health_url = urljoin(self.prometheus_url, "/-/healthy")
            async with self.session.get(health_url) as response:
                prometheus_healthy = response.status == 200
            
            # Check for Kepler metrics existence
            query = "up{job=~\"kepler.*\"}"
            kepler_metrics = await self._prometheus_query(query)
            kepler_healthy = len(kepler_metrics.get("data", {}).get("result", [])) > 0
            
            return {
                "prometheus": prometheus_healthy,
                "kepler": kepler_healthy,
                "status": "healthy" if prometheus_healthy and kepler_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "prometheus": False,
                "kepler": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _prometheus_query(self, query: str, time_range: Optional[str] = None) -> Dict[str, Any]:
        """Execute Prometheus query"""
        await self._ensure_session()
        
        query_url = urljoin(self.prometheus_url, "/api/v1/query")
        if time_range:
            query_url = urljoin(self.prometheus_url, "/api/v1/query_range")
        
        params = {"query": query}
        
        if time_range:
            # Add time range parameters
            end_time = datetime.utcnow()
            start_time = end_time - self._parse_time_range(time_range)
            
            params.update({
                "start": start_time.timestamp(),
                "end": end_time.timestamp(),
                "step": "30s"  # Collect data at 30-second intervals
            })
        
        try:
            async with self.session.get(query_url, params=params) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientError as e:
            logger.error(f"Prometheus query failed: {query}, error: {e}")
            raise
    
    def _parse_time_range(self, time_range: str) -> timedelta:
        """Convert time range string to timedelta"""
        if time_range.endswith('m'):
            return timedelta(minutes=int(time_range[:-1]))
        elif time_range.endswith('h'):
            return timedelta(hours=int(time_range[:-1]))
        elif time_range.endswith('d'):
            return timedelta(days=int(time_range[:-1]))
        else:
            return timedelta(minutes=5)  # Default: 5 minutes
    
    async def get_container_power_metrics(
        self,
        namespace: Optional[str] = None,
        workload: Optional[str] = None,
        time_range: str = "5m"
    ) -> List[ContainerPowerData]:
        """Collect power metrics by container"""
        try:
            # Base query
            base_query = "kepler_container_joules_total"
            
            # Add filter conditions
            filters = []
            if namespace:
                filters.append(f'container_namespace="{namespace}"')
            if workload:
                filters.append(f'pod_name=~".*{workload}.*"')
            
            if filters:
                query = f'{base_query}{{{",".join(filters)}}}'
            else:
                query = base_query
            
            # Execute Prometheus query
            result = await self._prometheus_query(query, time_range)
            
            # Parse results
            containers = []
            for series in result.get("data", {}).get("result", []):
                metric = series.get("metric", {})
                values = series.get("values", [])
                
                if values:
                    # Use latest value
                    latest_value = values[-1]
                    timestamp = datetime.fromtimestamp(float(latest_value[0]))
                    power_joules = float(latest_value[1])
                    
                    container_data = ContainerPowerData(
                        container_name=metric.get("container_name", "unknown"),
                        pod_name=metric.get("pod_name", "unknown"),
                        namespace=metric.get("container_namespace", "unknown"),
                        node_name=metric.get("instance", "unknown"),
                        power_joules=power_joules,
                        timestamp=timestamp,
                        labels=metric
                    )
                    containers.append(container_data)
            
            logger.info(f"Container power metrics collection completed: {len(containers)} items")
            return containers
            
        except Exception as e:
            logger.error(f"Container power metrics collection failed: {e}")
            raise
    
    async def get_all_container_metrics(
        self,
        namespace: Optional[str] = None,
        limit: int = 100
    ) -> List[ContainerPowerData]:
        """Collect power metrics for all containers"""
        try:
            # Collect various power metrics
            queries = {
                "total": "kepler_container_joules_total",
                "cpu": "kepler_container_cpu_joules_total",
                "gpu": "kepler_container_gpu_joules_total",
                "memory": "kepler_container_dram_joules_total",
                "other": "kepler_container_other_joules_total"
            }
            
            containers_map = {}
            
            for metric_type, base_query in queries.items():
                # Apply namespace filter
                if namespace:
                    query = f'{base_query}{{container_namespace="{namespace}"}}'
                else:
                    query = base_query
                
                result = await self._prometheus_query(query)
                
                # Process results
                for series in result.get("data", {}).get("result", []):
                    metric = series.get("metric", {})
                    value_data = series.get("value", [])
                    
                    if value_data and len(value_data) > 1:
                        container_key = (
                            metric.get("container_name", "unknown"),
                            metric.get("pod_name", "unknown"),
                            metric.get("container_namespace", "unknown")
                        )
                        
                        if container_key not in containers_map:
                            containers_map[container_key] = ContainerPowerData(\n                                container_name=container_key[0],\n                                pod_name=container_key[1],\n                                namespace=container_key[2],\n                                node_name=metric.get("instance", "unknown"),\n                                power_joules=0.0,\n                                timestamp=datetime.fromtimestamp(float(value_data[0])),\n                                labels=metric\n                            )\n                        \n                        # Set value by metric type\n                        setattr(\n                            containers_map[container_key], \n                            f\"{metric_type}_power_joules\", \n                            float(value_data[1])\n                        )\n            \n            # Convert results to list and apply limit\n            containers = list(containers_map.values())[:limit]\n            \n            logger.info(f\"All container metrics collection completed: {len(containers)}개\")\n            return containers\n            \n        except Exception as e:\n            logger.error(f\"All container metrics collection failed: {e}\")\n            raise\n    \n    async def get_node_power_metrics(self) -> List[NodePowerData]:\n        \"\"\"Collect power metrics by node\"\"\"\n        try:\n            # Node platform power metrics\n            query = \"kepler_node_platform_joules_total\"\n            result = await self._prometheus_query(query)\n            \n            nodes = []\n            for series in result.get(\"data\", {}).get(\"result\", []):\n                metric = series.get(\"metric\", {})\n                value_data = series.get(\"value\", [])\n                \n                if value_data and len(value_data) > 1:\n                    node_data = NodePowerData(\n                        node_name=metric.get(\"instance\", \"unknown\"),\n                        platform_power_joules=float(value_data[1]),\n                        timestamp=datetime.fromtimestamp(float(value_data[0])),\n                        labels=metric\n                    )\n                    nodes.append(node_data)\n            \n            # Collect additional node component metrics\n            await self._enrich_node_metrics(nodes)\n            \n            logger.info(f\"Node power metrics collection completed: {len(nodes)}개\")\n            return nodes\n            \n        except Exception as e:\n            logger.error(f\"Node power metrics collection failed: {e}\")\n            raise\n    \n    async def _enrich_node_metrics(self, nodes: List[NodePowerData]):\n        \"\"\"Collect additional node metrics information\"\"\"\n        # Component power metrics by node\n        component_queries = {\n            \"cpu\": \"kepler_node_cpu_joules_total\",\n            \"dram\": \"kepler_node_dram_joules_total\",\n            \"uncore\": \"kepler_node_uncore_joules_total\",\n            \"pkg\": \"kepler_node_package_joules_total\"\n        }\n        \n        node_map = {node.node_name: node for node in nodes}\n        \n        for component, query in component_queries.items():\n            try:\n                result = await self._prometheus_query(query)\n                \n                for series in result.get(\"data\", {}).get(\"result\", []):\n                    metric = series.get(\"metric\", {})\n                    value_data = series.get(\"value\", [])\n                    \n                    if value_data and len(value_data) > 1:\n                        node_name = metric.get(\"instance\", \"unknown\")\n                        if node_name in node_map:\n                            setattr(\n                                node_map[node_name],\n                                f\"{component}_power_joules\",\n                                float(value_data[1])\n                            )\n            \n            except Exception as e:\n                logger.warning(f\"노드 {component} metrics collection failed: {e}\")\n                continue\n    \n    async def get_workload_power_summary(self, workload_name: str) -> Dict[str, Any]:\n        \"\"\"Summary of power usage for a specific workload\"\"\"\n        try:\n            # Collect power data for workload-related containers\n            containers = await self.get_container_power_metrics(\n                workload=workload_name,\n                time_range=\"1h\"\n            )\n            \n            if not containers:\n                return {\n                    \"workload_name\": workload_name,\n                    \"total_power_joules\": 0.0,\n                    \"container_count\": 0,\n                    \"message\": \"Workload data not found\"\n                }\n            \n            # Calculate total power usage\n            total_power = sum(container.power_joules for container in containers)\n            \n            return {\n                \"workload_name\": workload_name,\n                \"total_power_joules\": total_power,\n                \"container_count\": len(containers),\n                \"containers\": [\n                    {\n                        \"name\": c.container_name,\n                        \"pod\": c.pod_name,\n                        \"namespace\": c.namespace,\n                        \"power_joules\": c.power_joules\n                    } for c in containers\n                ],\n                \"timestamp\": datetime.utcnow().isoformat()\n            }\n            \n        except Exception as e:\n            logger.error(f\"Workload power summary failed: {e}\")\n            raise