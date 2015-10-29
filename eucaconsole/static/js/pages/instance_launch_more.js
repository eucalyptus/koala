/**
 * @fileOverview Launch more like this instance page JS
 * @requires AngularJS
 *
 */

// Launch Instance page includes the Tag Editor, the Image Picker, and the Block Device Mapping editor
angular.module('LaunchMoreInstances', ['BlockDeviceMappingEditor'])
    .controller('LaunchMoreInstancesCtrl', function ($scope, $timeout) {
        $scope.form = $('#launch-more-form');
        $scope.instanceNumber = 1;
        $scope.expanded = false;
        $scope.toggleContent = function () {
            $scope.expanded = !$scope.expanded;
        };
        $scope.setInitialValues = function () {
            $('#number').val($scope.instanceNumber);
            if ($("#userdata").val().length > 0) {
                $scope.inputtype = "text";
            }
        };
        $scope.initController = function () {
            $scope.setInitialValues();
            $scope.$watch('inputtype', function(newValue, oldValue) {
                if (newValue != oldValue) {
                    if ($scope.inputtype == 'text') {
                        $timeout(function() {
                            $('#userdata').focus();
                        });
                    }
                }
            });
        };
        $scope.buildNumberList = function (limit) {
            // Return a 1-based list of integers of a given size ([1, 2, ... limit])
            limit = parseInt(limit, 10);
            var result = [];
            for (var i = 1; i <= limit; i++) {
                result.push(i);
            }
            return result;
        };
    })
;

