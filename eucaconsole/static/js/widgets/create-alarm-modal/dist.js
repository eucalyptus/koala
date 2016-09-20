angular.module('AlarmServiceModule', ['EucaRoutes'])
.factory('AlarmService', ['$http', 'eucaRoutes', function ($http, eucaRoutes) {
    $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

    return {
        createAlarm: function (alarm, csrf_token) {
            return eucaRoutes.getRouteDeferred('cloudwatch_alarms')
                .then(function (path) {
                    return $http({
                        method: 'PUT',
                        url: path,
                        data: {
                            alarm: alarm,
                            csrf_token: csrf_token
                        }
                    });
                });
        },

        updateAlarm: function (alarm, csrf_token, flash) {
            return eucaRoutes.getRouteDeferred('cloudwatch_alarms')
                .then(function (path) {
                    return $http({
                        method: 'PUT',
                        url: path,
                        data: {
                            alarm: alarm,
                            csrf_token: csrf_token,
                            flash: flash
                        }
                    });
                });
        },

        deleteAlarms: function (alarms, csrf_token, flash) {
            var alarmNames = alarms.map(function (current) {
                return current.name;
            });

            return eucaRoutes.getRouteDeferred('cloudwatch_alarms')
                .then(function (path) {
                    return $http({
                        method: 'DELETE',
                        url: path,
                        data: {
                            alarms: alarmNames,
                            csrf_token: csrf_token,
                            flash: flash
                        }
                    });
                });
        },

        updateActions: function (id, actions) {
            return eucaRoutes.getRouteDeferred('cloudwatch_alarm_actions', { alarm_id: id })
                .then(function (path) {
                    return $http({
                        method: 'PUT',
                        url: path,
                        data: {
                            actions: actions
                        }
                    });
                });
        },

        getHistory: function (id) {
            return eucaRoutes.getRouteDeferred('cloudwatch_alarm_history_json', { alarm_id: id })
                .then(function (path) {
                    return $http({
                        method: 'GET',
                        url: path
                    }).then(function (response) {
                        var data = response.data || {
                            history: []
                        };
                        return data.history;
                    });
                });
        },

        getAlarmsForResource: function (id, type) {
            return eucaRoutes.getRouteDeferred('cloudwatch_alarms_for_resource_json', { id: id })
                .then(function (path) {
                    return $http({
                        method: 'GET',
                        url: path,
                        params: {
                            'resource-type': type
                        }
                    }).then(function success (response) {
                        var data = response.data.results || [];
                        return data;
                    }, function error (response) {
                        return response;
                    });
                });
        }
    };
}]);

angular.module('MetricServiceModule', ['EucaRoutes'])
.factory('MetricService', ['$http', 'eucaRoutes', function ($http, eucaRoutes) {
    var _metrics = {};

    return {
        getMetrics: function (type, value) {
            if(value in _metrics) {
                return _metrics[value];
            }
            return eucaRoutes.getRouteDeferred('metrics_available_for_resource', {type: type, value: value})
                .then(function (path) {
                    return $http({
                        method: 'GET',
                        url: path
                    }).then(function (result) {
                        if(result && result.data) {
                            _metrics[value] = result.data.metrics;
                        }
                        return _metrics[value];
                    });
                });
        }
    };
}]);

angular.module('ScalingGroupsServiceModule', ['EucaRoutes'])
.factory('ScalingGroupsService', ['$http', 'eucaRoutes', function ($http, eucaRoutes) {
    return {
        getScalingGroups: function () {
            return eucaRoutes.getRouteDeferred('scalinggroup_names_json').then(function (path) {
                return $http({
                    method: 'GET',
                    url: path
                }).then(function success (response) {
                    var data = response.data || {
                        scalinggroups: []
                    };
                    return data.scalinggroups;
                }, function error (response) {
                    return response;
                });
            });
        },

        getPolicies: function (id) {
            return eucaRoutes.getRouteDeferred('scalinggroup_policies_json', { id: id }).then(function (path) {
                return $http({
                    method: 'GET',
                    url: path
                }).then(function success (response) {
                    var data = response.data || {
                        policies: {}
                    };
                    return data;
                }, function error (response) {
                    return response;
                });
            });
        }
    };
}]);

angular.module('ModalModule', [])
.directive('modal', ['ModalService', function (ModalService) {
    return {
        restrict: 'A',
        template: '<div class="modal-bg"></div><div class="modal-content"><a ng-click="closeModal()" class="close-modal">×</a><ng-transclude></ng-transclude></div>',
        transclude: true,
        link: function (scope, element, attrs) {
            scope.modalName = attrs.modal;
            ModalService.registerModal(scope.modalName, element);
        },
        controller: ['$scope', function ($scope) {
            $scope.closeModal = function () {
                ModalService.closeModal($scope.modalName);
            };
        }]
    };
}])
.factory('ModalService', ['$rootScope', function ($rootScope) {
    var _modals = {};

    function registerModal (name, element) {
        if(name in _modals) {
            console.error('Modal with name ', name, ' already registered.');
            return;
        }
        _modals[name] = element;
    }

    function openModal (name) {
        var modal = _modals[name];
        if(!modal) {
            return;
        }

        modal.addClass('open');
    }

    function closeModal (name) {
        var modal = _modals[name];
        if(!modal) {
            return;
        }

        modal.removeClass('open');
        $rootScope.$broadcast('modal:close', name);
    }

    return {
        openModal: openModal,
        closeModal: closeModal,
        registerModal: registerModal
    };
}]);

angular.module('AlarmActionsModule', ['AlarmServiceModule', 'ScalingGroupsServiceModule'])
.directive('alarmActions', function () {
    return {
        restrict: 'A',
        link: function (scope, element, attrs) {
            scope.alarmId = attrs.alarmId;
            scope.alarmActions = JSON.parse(attrs.alarmActions);
            scope.defaultOptionValue = 'Select policy...';
        },
        controller: ['$scope', 'AlarmService', 'ScalingGroupsService', function ($scope, AlarmService, ScalingGroupsService) {
            ScalingGroupsService.getScalingGroups().then(function (result) {
                $scope.scalingGroups = result;
            });

            $scope.addAction = function () {
                //  Do not add action if form is invalid
                if($scope.alarmActionsForm.$invalid || $scope.alarmActionsForm.$pristine) {
                    return;
                }

                var policyName = $scope.action.scalingGroupPolicy,
                    policy = $scope.scalingGroupPolicies[policyName];

                //  Do not add action if duplicate
                var duplicate = $scope.alarmActions.some(function (current) {
                    return current.arn == policy.arn && current.alarm_state == $scope.action.alarm_state;
                });
                if(duplicate) {
                    return;
                }

                var action = {
                    alarm_state: $scope.action.alarm_state,
                    autoscaling_group_name: $scope.action.scalingGroup,
                    policy_name: policyName,
                    arn: policy.arn,
                    scaling_adjustment: policy.scaling_adjustment
                };
                $scope.alarmActions.push(action);

                $scope.updateActions();
            };

            $scope.removeAction = function ($index) {
                $scope.alarmActions.splice($index, 1);
                $scope.updateActions();
            };

            $scope.updateActions = function () {
                $scope.$emit('actionsUpdated', $scope.alarmActions);
                $scope.resetForm();
            };

            $scope.resetForm = function () {
                $scope.action = {
                    alarm_state: 'ALARM'
                };
                $scope.defaultOptionValue = 'Select policy...';
                $scope.scalingGroupPolicies = [];
                $scope.alarmActionsForm.$setPristine();
                $scope.alarmActionsForm.$setUntouched();
            };

            $scope.policiesAvailable = function () {
                var policies = $scope.scalingGroupPolicies || {};
                return !Object.keys(policies).length;
            };

            $scope.updatePolicies = function () {
                if($scope.action.scalingGroup === '') {
                    $scope.resetForm();
                    return;
                }

                ScalingGroupsService.getPolicies($scope.action.scalingGroup)
                    .then(function success (data) {
                        var policies = data.policies || {},
                            filtered = {};

                        var availableKeys = Object.keys(policies).filter(function (key) {
                            return !$scope.alarmActions.some(function (action) {
                                return action.policy_name == key && action.alarm_state == $scope.action.alarm_state;
                            });
                        });

                        $scope.scalingGroupPolicies = {};
                        availableKeys.forEach(function (key) {
                            $scope.scalingGroupPolicies[key] = policies[key];
                        });

                        if(Object.keys(availableKeys).length < 1) {
                            $scope.defaultOptionValue = 'No policies available';
                        } else {
                            $scope.defaultOptionValue = 'Select policy...';
                        }
                    }, function error (response) {
                        console.log(response);
                    });
            };
        }]
    };
})
.directive('requiredIfChanged', function () {
    return {
        restrict: 'A',
        require: 'ngModel',
        link: function (scope, element, attrs, ctrl) {
            ctrl.$validators.requiredIfChanged = function (modelValue, viewValue) {
                if(ctrl.$touched && ctrl.$isEmpty(modelValue)) {
                    return false;
                }
                return true;
            };
        }
    };
})
.filter('signed', function () {
    return function (input) {
        input = Number(input);
        if(input > 0) {
            return '+' + input.toString(10);
        }
        return input.toString(10);
    };
});

angular.module('CreateAlarmModal', [
    'ModalModule',
    'AlarmServiceModule',
    'MetricServiceModule',
    'ScalingGroupsServiceModule',
    'AlarmActionsModule'
])
.directive('createAlarm', ['MetricService', 'AlarmService', function (MetricService, AlarmService) {
    var defaults = {};

    return {
        restrict: 'A',
        require: 'modal',
        link: function (scope, element, attrs) {
            defaults = {
                statistic: attrs.defaultStatistic,
                metric: attrs.defaultMetric,
                comparison: '>=',
            };

            scope.resourceType = attrs.resourceType;
            scope.resourceId = attrs.resourceId;
            scope.resourceName = attrs.resourceName;

            scope.$on('modal:close', function (event, name) {
                if(name == 'createAlarm') {
                    scope.resetForm();
                }
            });

            MetricService.getMetrics(scope.resourceType, scope.resourceId)
                .then(function (metrics) {
                    scope.metrics = metrics || [];

                    scope.alarm.metric = (function (metrics, defaultMetric) {
                        var metric;
                        for(var i = 0; i < metrics.length; i++ ) {
                            metric = metrics[i];
                            if(metric.name == defaultMetric) {
                                break;
                            }
                        }
                        return metric;
                    }(scope.metrics, attrs.defaultMetric));

                    scope.alarm.statistic = attrs.defaultStatistic;
                    scope.alarm.comparison = '>=';

                    defaults.metric = scope.alarm.metric;
                });

            scope.checkNameCollision();
        },
        controller: ['$scope', '$rootScope', 'AlarmService', 'ModalService', function ($scope, $rootScope, AlarmService, ModalService) {
            $scope.alarm = {};
            var csrf_token = $('#csrf_token').val();

            $scope.onNameChange = function () {
                $scope.createAlarmForm.name.$setTouched();
            };

            $scope.$watchCollection('alarm', function (newVal) {
                if(newVal.metric && $scope.createAlarmForm.name.$untouched) {
                    $scope.alarm.name = $scope.alarmName();
                }
            });

            $scope.alarmName = function (count) {
                // Name field updates when metric selection changes,
                // unless the user has changed the value themselves.
                count = count || 0;
                if(count > 20) {
                    $scope.createAlarmForm.name.$setValidity('uniqueName', false);
                    return $scope.alarm.name;
                }
                
                var alarm = $scope.alarm;
                var name = [
                    alarm.metric.namespace,
                    $scope.resourceName || $scope.resourceId,
                    alarm.metric.name].join(' - ');

                if(count > 0) {
                    name = name + [' (', ')'].join(count);
                }

                var collision = $scope.existingAlarms.some(function (alarm) {
                    return alarm.name == name;
                });

                if(collision) {
                    name = $scope.alarmName(count + 1);
                }

                return name;
            };

            $scope.createAlarm = function () {
                if($scope.createAlarmForm.$invalid) {
                    return;
                }

                var alarm = $scope.alarm;

                AlarmService.createAlarm({
                    name: alarm.name,
                    metric: alarm.metric.name,
                    namespace: alarm.metric.namespace,
                    statistic: alarm.statistic,
                    comparison: alarm.comparison,
                    threshold: alarm.threshold,
                    period: alarm.period,
                    evaluation_periods: alarm.evaluation_periods,
                    unit: alarm.unit,
                    description: alarm.description,
                    dimensions: alarm.metric.dimensions,
                    alarm_actions: alarm.alarm_actions,
                    insufficient_data_actions: alarm.insufficient_data_actions,
                    ok_actions: alarm.ok_actions
                }, csrf_token).then(function success (response) {
                    ModalService.closeModal('createAlarm');
                    Notify.success(response.data.message);
                    $rootScope.$broadcast('alarmStateView:refreshList');
                }, function error (response) {
                    ModalService.closeModal('createAlarm');
                    Notify.failure(response.data.message);
                });
            };

            $scope.$on('actionsUpdated', function (event, actions) {
                var targets = {
                    ALARM: 'alarm_actions',
                    INSUFFICIENT_DATA: 'insufficient_data_actions',
                    OK: 'ok_actions'
                };
                $scope.alarm.insufficient_data_actions = [];
                $scope.alarm.alarm_actions = [];
                $scope.alarm.ok_actions = [];

                actions.forEach(function (action) {
                    var target = targets[action.alarm_state];
                    $scope.alarm[target].push(action.arn);
                });
            });

            $scope.resetForm = function () {
                $scope.alarm = angular.copy(defaults);
                $scope.createAlarmForm.$setPristine();
                $scope.createAlarmForm.$setUntouched();
                $scope.checkNameCollision();
            };

            $scope.checkNameCollision = function () {
                $scope.existingAlarms = [];
                AlarmService.getAlarmsForResource($scope.resourceId, $scope.resourceType)
                    .then(function (alarms) {
                        $scope.existingAlarms = alarms;
                        $scope.alarm.name = $scope.alarmName();
                    });
                };
        }]
    };
}]);

//# sourceMappingURL=dist.js.map