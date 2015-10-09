/**
 * @fileOverview Scaling group Instances page JS
 * @requires AngularJS
 *
 */

angular.module('ScalingGroupInstances', ['EucaConsoleUtils'])
    .controller('ScalingGroupInstancesCtrl', function ($scope, $http, $timeout, eucaHandleError) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.loading = false;
        $scope.items = [];
        $scope.instanceID = '';
        $scope.jsonEndpoint = '';
        $scope.initialLoading = true;
        $scope.initController = function (jsonEndpoint) {
            $scope.jsonEndpoint = jsonEndpoint;
            $scope.getItems();
            $scope.setFocus();
        };
        $scope.getItems = function () {
            $http.get($scope.jsonEndpoint).success(function(oData) {
                var transitionalCount = 0;
                $scope.items = oData ? oData.results : [];
                $scope.initialLoading = false;
                $scope.items.forEach(function (item) {
                    if (item.transitional) {
                        transitionalCount += 1;
                    }
                });
                // Auto-refresh instances if any of them are in transition
                if (transitionalCount > 0) {
                    $timeout(function() { $scope.getItems(); }, 5000);  // Poll every 5 seconds
                }
            }).error(function (oData, status) {
                eucaHandleError(oData, status);
            });
        };
        $scope.revealModal = function (action, item) {
            var modal = $('#' + action + '-instance-modal');
            $scope.instanceID = item.id;
            modal.foundation('reveal', 'open');
        };
        $scope.setFocus = function () {
            $(document).on('opened.fndtn.reveal', '[data-reveal]', function () {
                var modal = $(this);
                var inputElement = modal.find('input[type!=hidden]').get(0);
                var modalButton = modal.find('button').get(0);
                if (!!inputElement) {
                    inputElement.focus();
                } else if (!!modalButton) {
                    modalButton.focus();
                }
            });
        };
    })
;

