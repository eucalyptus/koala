"""
URL dispatch routes

The route names and patterns are listed here.
The routes are wired up to view callables via the view_config decorator, which attaches a view to the route_name.

For example, the 'instances' route name is connected to the Instances landing page as follows...

    @view_config(route_name='instances', renderer='../templates/instances/instances.pt')
    def instances_landing(self):
        pass

"""
from collections import namedtuple


# Simple container to hold a route name and pattern
Route = namedtuple('Route', ['name', 'pattern'])

urls = [
    Route(name='dashboard', pattern='/'),
    Route(name='login', pattern='/login'),
    Route(name='logout', pattern='/logout'),
    # Common
    Route(name='region_select', pattern='/region/select'),
    # Instances
    Route(name='instances', pattern='/instances'),
    Route(name='instances_json', pattern='/instances/json'),
    Route(name='instance_view', pattern='/instances/{id}'),
    # Scaling Groups
    Route(name='scalinggroups', pattern='/scalinggroups'),
    Route(name='scalinggroups_json', pattern='/scalinggroups/json'),
    # Launch Configurations
    Route(name='launchconfigs', pattern='/launchconfigs'),
    Route(name='launchconfigs_json', pattern='/launchconfigs/json'),
    # Volumes
    Route(name='volumes', pattern='/volumes'),
    Route(name='volumes_json', pattern='/volumes/json'),
    # Snapshots
    Route(name='snapshots', pattern='/snapshots'),
    Route(name='snapshots_json', pattern='/snapshots/json'),
    # Security Groups
    Route(name='securitygroups', pattern='/securitygroups'),
    Route(name='securitygroups_json', pattern='/securitygroups/json'),
    # Key pairs
    Route(name='keypairs', pattern='/keypairs'),
    Route(name='keypairs_json', pattern='/keypairs/json'),
    # IP Addresses
    Route(name='ipaddresses', pattern='/ipaddresses'),
    Route(name='ipaddresses_json', pattern='/ipaddresses/json'),
]
