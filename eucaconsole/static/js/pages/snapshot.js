/**
 * @fileOverview Snapshot detail page JS
 * @requires AngularJS
 *
 */

// Snapshot page includes the tag editor, so pull in that module as well.
angular.module('SnapshotPage', ['TagEditor'])
    .controller('SnapshotPageCtrl', function ($scope, $http, $timeout) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.snapshotStatusEndpoint = '';
        $scope.transitionalStates = ['pending', 'deleting'];
        $scope.snapshotStatus = '';
        $scope.snapshotProgress = '';
        $scope.isNotChanged = true;
        $scope.isSubmitted = false;
        $scope.isUpdating = false;
        $scope.imagesURL = '';
        $scope.images = undefined;
        $scope.isTransitional = function (state) {
            return $scope.transitionalStates.indexOf(state) !== -1;
        };
        $scope.inProgress = function (progress) {
            progress = parseInt(progress.replace('%', ''), 10);
            return progress < 100
        };
        $scope.initChosenSelector = function () {
            $(document).ready(function() {
                $('#volume_id').chosen({'width': '75%', search_contains: true});
                $('#volume_id').val('').trigger('chosen:updated'); 
            });
        };
        $scope.initController = function (jsonEndpoint, status, progress, volumeCount, imagesURL) {
            $scope.displayVolumeWarning(volumeCount);
            $scope.initChosenSelector();
            $scope.snapshotStatusEndpoint = jsonEndpoint;
            $scope.snapshotStatus = status;
            $scope.snapshotProgress = progress;
            $scope.imagesURL = imagesURL;
            if (jsonEndpoint) {
                $scope.getSnapshotState();
            }
            $scope.setWatch();
            $scope.setFocus();
        };
        $scope.displayVolumeWarning = function (volumeCount) {
            if (volumeCount === 0) {
                $('#create-warn-modal').foundation('reveal', 'open');
            }
        };
        $scope.getSnapshotState = function () {
            $http.get($scope.snapshotStatusEndpoint).success(function(oData) {
                var results = oData ? oData.results : '';
                if (results) {
                    $scope.snapshotStatus = results['status'];
                    $scope.snapshotProgress = results['progress'];
                    if ($scope.snapshotStatus == 'failed') {
                        $scope.isUpdating = false;
                        return true;
                    }
                    // Poll to obtain desired end state if current state is transitional or snapshot is in progress
                    if ($scope.isTransitional($scope.snapshotStatus) || $scope.inProgress($scope.snapshotProgress)) {
                        $scope.isUpdating = true;
                        $timeout(function() {$scope.getSnapshotState()}, 5000);  // Poll every 5 seconds
                    } else {
                        $scope.isUpdating = false;
                    }
                }
            }).error(function (oData, status) {
                var errorMsg = oData['message'] || null;
                if (errorMsg && status === 403) {
                    $('#timed-out-modal').foundation('reveal', 'open');
                }
            });
        };
        $scope.setWatch = function () {
            $scope.$on('tagUpdate', function($event) {
                $scope.isNotChanged = false;
            });
            $(document).on('input', 'input[type="text"]', function () {
                $scope.isNotChanged = false;
                $scope.$apply();
            });
            $(document).on('submit', '[data-reveal] form', function () {
                $(this).find('.dialog-submit-button').css('display', 'none');                
                $(this).find('.dialog-progress-display').css('display', 'block');                
            });
            $(document).on('submit', function () {
                $scope.isSubmitted = true;
            });
            window.addEventListener("beforeunload", function(event) {
                var existsUnsavedTag = false;
                $('input.taginput').each(function(){
                    if($(this).val() !== ''){
                        existsUnsavedTag = true;
                    }
                });
                if(existsUnsavedTag){
                    return "You must click the \"Add\" button before you submit this for your tag to be included.";
                }else if($scope.isNotChanged === false){
                    if( $scope.isSubmitted === true ){
                        return;
                    }
                    return "You must click the \"Save Changes\" button before you leave this page.";
                }
            });
        };
        $scope.setFocus = function () {
            $(document).on('ready', function(){
                var actionsMenu = $('.actions-menu');
                if (actionsMenu.length) {
                    actionsMenu.find('a').get(0).focus();
                }else if( $('input[type="text"]').length > 0 ){
                    $('input[type="text"]').get(0).focus();
                }
            });
            $(document).on('opened', '[data-reveal]', function () {
                var modal = $(this);
                var modalID = $(this).attr('id');
                if( modalID.match(/terminate/)  || modalID.match(/delete/) || modalID.match(/release/) ){
                    var closeMark = modal.find('.close-reveal-modal');
                    if(!!closeMark){
                        closeMark.focus();
                    }
                }else{
                    var inputElement = modal.find('input[type!=hidden]').get(0);
                    var modalButton = modal.find('button').get(0);
                    if (!!inputElement) {
                        inputElement.focus();
                    } else if (!!modalButton) {
                        modalButton.focus();
                    }
               }
            });
        };
        $scope.deleteModal = function () {
            var modal = $('#delete-snapshot-modal');
            $scope.images = undefined;
            $scope.getSnapshotImages($scope.imagesURL);
            modal.foundation('reveal', 'open');
            modal.find('h3').click();
        };
        $scope.getSnapshotImages = function (url) {
            $http.get(url).success(function(oData) {
                var results = oData ? oData.results : '';
                if (results && results.length > 0) {
                    $scope.images = results;
                }
            }).error(function (oData, status) {
                var errorMsg = oData['message'] || null;
                if (errorMsg && status === 403) {
                    $('#timed-out-modal').foundation('reveal', 'open');
                }
            });
        };
    })
;

