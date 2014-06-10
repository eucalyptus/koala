/**
 * @fileOverview SecurityGroup Detail Page JS
 * @requires AngularJS
 *
 */

angular.module('SecurityGroupPage', ['TagEditor', 'SecurityGroupRules'])
    .controller('SecurityGroupPageCtrl', function ($scope) {
        $scope.isNotValid = true;
        $scope.isNotChanged = true;
        $scope.securityGroupName = undefined;
        $scope.securityGroupDescription = undefined;
        $scope.initController = function () {
            $scope.setWatch();
            $scope.setFocus();
        };
        $scope.checkRequiredInput = function () {
            if($scope.securityGroupName === undefined || $scope.securityGroupDescription === undefined){
               $scope.isNotValid = true;
            } else {
               $scope.isNotValid = false;
            }
        };
        $scope.setWatch = function () {
            $scope.$watch('securityGroupName', function () {
                $scope.checkRequiredInput(); 
            });
            $scope.$watch('securityGroupDescription', function () {
                $scope.checkRequiredInput();
            });
            // Handle the unsaved tag issue
            $(document).on('submit', '#security-group-detail-form', function(event) {
                $('input.taginput').each(function(){
                    if($(this).val() !== ''){
                        event.preventDefault(); 
                        $('#unsaved-tag-warn-modal').foundation('reveal', 'open');
                        return false;
                    }
                });
            });
            $(document).on('submit', '[data-reveal] form', function () {
                $(this).find('.dialog-submit-button').css('display', 'none');                
                $(this).find('.dialog-progress-display').css('display', 'block');                
            });
        };
        $scope.setFocus = function () {
            $scope.$on('tagUpdate', function($event) {
                $scope.isNotChanged = false;
            });
            $scope.$on('securityGroupUpdate', function($event) {
                $scope.isNotChanged = false;
            });
            $(document).on('ready', function(){
                var firstLink = $('.actions-menu').find('a');
                if( firstLink.length > 0 ){
                    firstLink.get(0).focus();
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
    })
;



